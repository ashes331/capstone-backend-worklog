"""
음성 주문 액션 도구 — DB 미사용, 액션 발행 전용.

각 도구는 입력 검증(카탈로그 대조) → push_action() → 사람이 읽을 확인 문자열 반환.
ACTION_TOOLS 리스트를 agent.py 에서 import 해 사용한다.
"""
from __future__ import annotations

from langchain_core.tools import tool

from .action_context import get_cart, push_action
from .menu_catalog import (
    SET_DRINKS,
    SET_SIDES,
    SET_SURCHARGE,
    get_menu,
)


@tool
def add_item(
    menu_id: int,
    item_type: str = "single",
    quantity: int = 1,
    exclusion: str = "없음",
    side: str | None = None,
    drink: str | None = None,
    special_note: str | None = None,
) -> str:
    """장바구니에 메뉴를 담는다.

    Args:
        menu_id: 카탈로그 숫자 ID (1~23). 카탈로그에 없는 ID 는 거부된다.
        item_type: 'single'(단품) 또는 'set'(세트). 세트는 has_set=True 메뉴만 가능.
        quantity: 담을 수량 (1 이상).
        exclusion: 제외 옵션. 카탈로그의 exclusions 목록 중 하나. 기본 '없음'.
        side: 세트 사이드 이름 (감자튀김/치즈스틱/치킨너겟/양념감자튀김). 미지정 시 기본값.
        drink: 세트 음료 이름 (콜라/제로콜라/사이다/제로사이다/생수/뽀로로음료/오렌지주스). 미지정 시 기본값.
        special_note: 주방 전달 비정형 요구사항 ("반으로 잘라주세요" 등). 생략 가능.
    """
    menu = get_menu(menu_id)
    if menu is None:
        return f"오류: 카탈로그에 ID {menu_id} 메뉴가 없습니다. 정확한 메뉴 ID 를 사용하세요."

    if quantity < 1:
        return "오류: 수량은 1 이상이어야 합니다."

    if item_type not in ("single", "set"):
        return "오류: item_type 은 'single' 또는 'set' 이어야 합니다."

    if item_type == "set" and not menu["has_set"]:
        return f"오류: {menu['name']}은(는) 세트 주문이 불가능합니다."

    # exclusion 유효성 검증 — 카탈로그에 없으면 '없음' 폴백
    valid_exclusions = menu["exclusions"]
    if exclusion not in valid_exclusions:
        exclusion = "없음"

    # 세트 옵션 기본값 보정
    resolved_side: str | None = None
    side_extra: int = 0
    resolved_drink: str | None = None
    drink_extra: int = 0

    if item_type == "set":
        side_names = [s["name"] for s in SET_SIDES]
        if side and side in side_names:
            idx = side_names.index(side)
            resolved_side = SET_SIDES[idx]["name"]
            side_extra = SET_SIDES[idx]["extra"]
        else:
            resolved_side = SET_SIDES[0]["name"]  # 기본값: 감자튀김
            side_extra = SET_SIDES[0]["extra"]

        drink_names = [d["name"] for d in SET_DRINKS]
        if drink and drink in drink_names:
            idx = drink_names.index(drink)
            resolved_drink = SET_DRINKS[idx]["name"]
            drink_extra = SET_DRINKS[idx]["extra"]
        else:
            resolved_drink = SET_DRINKS[0]["name"]  # 기본값: 콜라
            drink_extra = SET_DRINKS[0]["extra"]

    action: dict = {
        "type": "add_item",
        "menu_id": menu_id,
        "name": menu["name"],
        "item_type": item_type,
        "quantity": quantity,
        "exclusion": exclusion,
        "side": resolved_side,
        "drink": resolved_drink,
    }
    if special_note:
        action["special_note"] = special_note

    push_action(action)

    type_label = "단품" if item_type == "single" else "세트"
    msg = f"{menu['name']}({type_label}) {quantity}개 담음"
    if item_type == "set":
        msg += f" [사이드: {resolved_side}, 음료: {resolved_drink}]"
    if exclusion != "없음":
        msg += f" [{exclusion}]"
    if special_note:
        msg += f" [특이사항: {special_note}]"
    return msg


@tool
def update_qty(menu_id: int, quantity: int, cart_id: float | None = None) -> str:
    """장바구니의 특정 메뉴 수량을 변경한다.

    Args:
        menu_id: 수량을 바꿀 메뉴의 카탈로그 ID.
        quantity: 새 수량. 0 이하이면 삭제됨(remove_item 사용 권장).
        cart_id: 같은 메뉴가 옵션별로 여러 줄이면 context의 cart_id로 정확한 줄 지정.
    """
    menu = get_menu(menu_id)
    if menu is None:
        return f"오류: 카탈로그에 ID {menu_id} 메뉴가 없습니다."

    cart = get_cart()
    exists = any(c.get("menu_id") == menu_id for c in cart)
    if not exists:
        return f"장바구니에 {menu['name']}이(가) 없습니다."

    match = {"cart_id": cart_id} if cart_id is not None else {"menu_id": menu_id}
    push_action({"type": "update_qty", "match": match, "quantity": quantity})
    return f"{menu['name']} 수량을 {quantity}개로 변경"


@tool
def update_item(
    cart_id: float,
    item_type: str | None = None,
    quantity: int | None = None,
    exclusion: str | None = None,
    side: str | None = None,
    drink: str | None = None,
) -> str:
    """이미 담긴 장바구니 항목의 옵션을 제자리에서 변경한다(삭제 후 재담기 아님).

    음료/사이드/제외/수량/단품·세트를 바꿀 때 사용. 변경할 필드만 채운다.
    반드시 context의 cart_id로 대상 줄을 지정한다.

    Args:
        cart_id: 변경할 장바구니 줄의 cart_id (context에 표시됨).
        item_type: 'single'|'set' 로 변경 시.
        quantity: 수량 변경 시.
        exclusion: 제외 옵션 변경 시 (예: '양상추 제외').
        side: 세트 사이드 변경 시 (예: '치킨너겟').
        drink: 세트 음료 변경 시 (예: '생수').
    """
    cart = get_cart()
    target = next((c for c in cart if c.get("cart_id") == cart_id), None)
    if target is None:
        return f"오류: cart_id {cart_id} 항목이 장바구니에 없습니다."

    action: dict = {"type": "update_item", "match": {"cart_id": cart_id}}
    if item_type in ("single", "set"):
        action["item_type"] = item_type
    if quantity is not None:
        action["quantity"] = quantity
    if exclusion is not None:
        action["exclusion"] = exclusion
    if side is not None:
        action["side"] = side
    if drink is not None:
        action["drink"] = drink

    push_action(action)
    name = target.get("name", "메뉴")
    changed = side or drink or exclusion or (f"{quantity}개" if quantity else None) or item_type or "옵션"
    return f"{name} {changed}(으)로 변경"


@tool
def remove_item(menu_id: int, cart_id: float | None = None) -> str:
    """장바구니에서 특정 메뉴를 삭제한다.

    Args:
        menu_id: 삭제할 메뉴의 카탈로그 ID.
        cart_id: 같은 메뉴가 옵션별로 여러 줄이면 context의 cart_id로 정확한 줄 지정.
                 (예: "F버거 생수 세트"처럼 옵션으로 특정하는 경우 해당 줄의 cart_id 사용)
    """
    menu = get_menu(menu_id)
    if menu is None:
        return f"오류: 카탈로그에 ID {menu_id} 메뉴가 없습니다."

    cart = get_cart()
    exists = any(c.get("menu_id") == menu_id for c in cart)
    if not exists:
        return f"장바구니에 {menu['name']}이(가) 없습니다."

    match = {"cart_id": cart_id} if cart_id is not None else {"menu_id": menu_id}
    push_action({"type": "remove_item", "match": match})
    return f"{menu['name']} 삭제"


@tool
def clear_cart() -> str:
    """장바구니를 전부 비운다."""
    push_action({"type": "clear_cart"})
    return "장바구니를 비웠습니다."


@tool
def navigate(screen: str) -> str:
    """화면을 이동한다.

    Args:
        screen: 이동할 화면 이름. 'menu'(메뉴), 'cart'(장바구니) 등.
    """
    push_action({"type": "navigate", "screen": screen})
    return f"{screen} 화면으로 이동"


@tool
def checkout(method: str | None = None) -> str:
    """결제를 진행한다. 장바구니가 비어있으면 거부한다.

    Args:
        method: 결제 수단 ('card'/'cash'/'pay' 등). 생략 가능. MVP 에서는 참고용.
    """
    cart = get_cart()
    if not cart:
        return "담긴 메뉴가 없어요. 먼저 메뉴를 선택해 주세요."

    action: dict = {"type": "checkout"}
    if method:
        action["method"] = method
    push_action(action)
    return "결제 화면(장바구니)으로 이동합니다."


# ── ui_action: 화면 조작 범용 도구 ──────────────────────────────────────────
# action 별 허용 value 화이트리스트. None = value 불필요.
_UI_ACTION_SPEC: dict[str, set[str] | None] = {
    "update_modal": None,    # field + field_value 로 처리 (아래 참고)
    "order_type": {"dine-in", "takeout"},
    "select_category": {"recommended", "burger", "side", "drink"},
    "menu_page": {"next", "prev"},
    "open_item": None,          # value = 메뉴 ID (숫자 문자열)
    "start_checkout": None,
    "points": {"yes", "no"},
    "points_phone": None,       # value = 전화번호
    "payment_method": {"card", "cash", "pay"},
    "set_language": {"ko", "en", "zh", "ja"},
    "set_gesture": {"on", "off"},
    "set_camera": {"on", "off"},
}

# 사람이 읽을 확인 메시지(간단)
_UI_ACTION_MSG: dict[str, str] = {
    "update_modal": "팝업 선택 변경",
    "order_type": "주문 유형 선택",
    "select_category": "메뉴 카테고리 이동",
    "menu_page": "메뉴 페이지 이동",
    "open_item": "메뉴 상세 열기",
    "start_checkout": "결제 시작",
    "points": "포인트 적립 선택",
    "points_phone": "전화번호 입력",
    "payment_method": "결제 수단 선택",
    "set_language": "언어 변경",
    "set_gesture": "제스처 설정",
    "set_camera": "카메라 미리보기 설정",
}


@tool
def ui_action(action: str, value: str | None = None, item_type: str | None = None,
              field: str | None = None, field_value: str | None = None) -> str:
    """화면 UI 를 조작하는 범용 도구. 현재 화면에 맞는 action 만 호출한다.

    action 종류와 파라미터:
      - update_modal (field: qty|exclusion|side|drink, field_value: 변경값)
                                                         : 열린 팝업의 선택 변경
                                                           예) field=side, field_value=양념감자튀김
      - order_type (value: dine-in | takeout)            : 매장/포장 선택 후 메뉴로
      - select_category (value: recommended|burger|side|drink) : 메뉴 카테고리 전환 (menu 화면)
      - menu_page (value: next | prev)                   : 메뉴 페이지 이동 (menu 화면)
      - open_item (value: 메뉴 ID 숫자, item_type: single|set 선택사항)
                                                         : 메뉴 상세 모달 표시 (menu 화면)
      - start_checkout                                   : 결제 시작 (cart 화면)
      - points (value: yes | no)                         : 포인트 적립 여부 (cart 화면)
      - points_phone (value: 전화번호)                   : 포인트 적립 전화번호 입력 (cart 화면)
      - payment_method (value: card | cash | pay)        : 결제 수단 선택 (cart 화면)
      - set_language (value: ko | en | zh | ja)          : 화면 언어 변경
      - set_gesture (value: on | off)                    : 손동작 인식 켜기/끄기
      - set_camera (value: on | off)                     : 카메라 미리보기 켜기/끄기

    다른 화면 기능이 필요하면 navigate 로 먼저 이동한 뒤 호출한다.
    """
    if action not in _UI_ACTION_SPEC:
        return f"오류: 지원하지 않는 action '{action}' 입니다."

    allowed = _UI_ACTION_SPEC[action]
    if allowed is not None:
        if value not in allowed:
            return (
                f"오류: action '{action}' 의 value 는 {sorted(allowed)} 중 하나여야 합니다."
            )
    elif action in ("open_item", "points_phone") and not value:
        return f"오류: action '{action}' 은 value 가 필요합니다."

    payload: dict = {"type": action}
    if action == "update_modal":
        _MODAL_FIELDS = {"qty", "exclusion", "side", "drink"}
        if not field or field not in _MODAL_FIELDS:
            return f"오류: update_modal 의 field 는 {sorted(_MODAL_FIELDS)} 중 하나여야 합니다."
        if not field_value:
            return "오류: update_modal 에는 field_value 가 필요합니다."
        payload["field"]       = field
        payload["value"]       = field_value
    elif action == "open_item":
        # 카탈로그 검증
        try:
            menu_id = int(value)
        except (TypeError, ValueError):
            return "오류: open_item 의 value 는 메뉴 ID 숫자여야 합니다."
        if get_menu(menu_id) is None:
            return f"오류: 카탈로그에 ID {menu_id} 메뉴가 없습니다."
        payload["menu_id"] = menu_id
        if item_type in ("single", "set"):
            payload["item_type"] = item_type
    elif action == "points_phone":
        payload["phone"] = value
    elif value is not None:
        payload["value"] = value

    push_action(payload)
    label = _UI_ACTION_MSG.get(action, action)
    detail = f" ({field}={field_value})" if action == "update_modal" else (f" ({value})" if value else "")
    return f"{label} 완료{detail}"


ACTION_TOOLS = [
    add_item,
    update_qty,
    update_item,
    remove_item,
    clear_cart,
    navigate,
    checkout,
    ui_action,
]
