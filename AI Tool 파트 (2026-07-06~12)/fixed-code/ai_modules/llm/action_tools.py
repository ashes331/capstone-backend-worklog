"""음성 주문 액션 도구 — DB API 연동 버전."""
from __future__ import annotations

import asyncio
import concurrent.futures
from langchain_core.tools import tool

# 세션 및 API 클라이언트 불러오기
from .action_context import push_action, get_session_id
from . import api_client

def _run(coro):
    """LangChain 동기 tool에서 비동기(async) API 클라이언트를 호출하기 위한 헬퍼."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except Exception:
        return asyncio.run(coro)

@tool
def list_menu() -> str:
    """판매 중인 메뉴 목록을 menu_item_id와 함께 조회한다. add_item 호출 전 menu_item_id 확인용으로 사용."""
    try:
        items = _run(api_client.fetch_menu_items())
    except Exception as e:
        return f"오류: 메뉴 조회 실패 — {e}"

    if not items:
        return "조회된 메뉴가 없습니다."

    lines = ["[메뉴 목록]"]
    for item in items:
        status = " [품절]" if not item.get("is_available", True) else ""
        lines.append(f"- {item['name_ko']} {int(float(item['base_price']))}원 (menu_item_id: {item['id']}){status}")
    return "\n".join(lines)

@tool
def add_item(
    menu_item_id: str,
    quantity: int = 1,
    upgrade_to_set: bool = False,
    exclusions: list[str] | None = None,
    special_note: str | None = None,
) -> str:
    """장바구니에 메뉴를 담는다.
    Args:
        menu_item_id: DB의 메뉴 UUID. 숫자가 아닌 문자열 UUID 형태임.
        quantity: 담을 수량 (1 이상).
        upgrade_to_set: True이면 세트 업그레이드 옵션 자동 추가.
        exclusions: 제외할 재료 이름 목록. 예: ["양파", "양상추"]
        special_note: 주방 전달 비정형 요구사항. 예: "반으로 잘라주세요"
    """
    session_id = get_session_id()

    try:
        # 단건 조회 API 호출
        item = _run(api_client.fetch_menu_item_by_id(menu_item_id))
    except Exception as e:
        return f"오류: 메뉴 조회 실패 — {e}"

    if item is None:
        return f"오류: 해당 ID의 메뉴를 찾을 수 없습니다 ({menu_item_id})"

    if not item.get("is_available", True):
        return f"죄송합니다, {item['name_ko']}는 현재 품절입니다."

    # 옵션 구성 로직
    selected_options = []
    options = item.get("options", [])

    if upgrade_to_set:
        set_opt = next((o for o in options if "세트" in o["name_ko"]), None)
        if set_opt:
            selected_options.append({"option_id": set_opt["id"], "name": set_opt["name_ko"]})
        else:
            return f"오류: {item['name_ko']}는 세트 주문이 불가합니다."

    for excl in (exclusions or []):
        opt = next((o for o in options if excl in o["name_ko"] and o.get("is_available", True)), None)
        if opt:
            selected_options.append({"option_id": opt["id"], "name": opt["name_ko"]})

    payload = {
        "menu_item_id": menu_item_id,
        "quantity": quantity,
        "selected_options": selected_options,
        "special_note": special_note,
    }

    try:
        # 장바구니 추가 API 호출
        result = _run(api_client.add_cart_item(session_id, payload))
    except Exception as e:
        return f"오류: 장바구니 추가 실패 — {e}"

    cart_item_id = result.get("cart_item_id")

    # 프론트엔드 액션 큐 반영 (화면 업데이트용)
    push_action({
        "type": "add_item",
        "menu_item_id": menu_item_id,
        "name": item["name_ko"],
        "quantity": quantity,
        "upgrade_to_set": upgrade_to_set,
        "exclusions": exclusions or [],
        "cart_item_id": cart_item_id,
    })

    type_label = "세트" if upgrade_to_set else "단품"
    msg = f"{item['name_ko']}({type_label}) {quantity}개 담음"
    if exclusions:
        msg += f" [{', '.join(exclusions)} 제외]"
    if special_note:
        msg += f" [특이사항: {special_note}]"
    return msg

@tool
def remove_item(cart_item_id: str) -> str:
    """장바구니에서 특정 항목을 삭제한다.
    Args:
        cart_item_id: 삭제할 장바구니 항목의 UUID. get_cart_status로 확인 가능.
    """
    session_id = get_session_id()
    try:
        _run(api_client.remove_cart_item(session_id, cart_item_id))
    except Exception as e:
        return f"오류: 삭제 실패 — {e}"

    push_action({"type": "remove_item", "cart_item_id": cart_item_id})
    return "항목을 장바구니에서 삭제했습니다."

@tool
def update_item_options(
    cart_item_id: str,
    quantity: int | None = None,
    exclusions: list[str] | None = None,
    special_note: str | None = None,
) -> str:
    """장바구니 항목의 수량 또는 옵션을 변경한다.
    Args:
        cart_item_id: 변경할 장바구니 항목 UUID.
        quantity: 새 수량.
        exclusions: 새 제외 옵션 목록.
        special_note: 새 특이사항.
    """
    session_id = get_session_id()
    payload: dict = {}
    if quantity is not None:
        payload["quantity"] = quantity
    if special_note is not None:
        payload["special_note"] = special_note

    try:
        _run(api_client.patch_cart_item(session_id, cart_item_id, payload))
    except Exception as e:
        return f"오류: 수정 실패 — {e}"

    push_action({"type": "update_item", "cart_item_id": cart_item_id, **payload})
    return "장바구니 항목을 수정했습니다."

@tool
def get_cart_status() -> str:
    """현재 장바구니 내용을 조회한다. 항목 수정·삭제 전에 cart_item_id 확인용으로 필수 사용."""
    session_id = get_session_id()
    try:
        cart = _run(api_client.get_cart(session_id))
    except Exception as e:
        return f"오류: 장바구니 조회 실패 — {e}"

    items = cart.get("items", [])
    if not items:
        return "장바구니가 비어있습니다."

    lines = ["[현재 장바구니]"]
    for item in items:
        opts = ", ".join(o["name"] for o in item.get("selected_options", []))
        line = f"- {item['name_ko']} x{item['quantity']} ({int(float(item['unit_price']))}원)"
        if opts:
            line += f" [{opts}]"
        if item.get("special_note"):
            line += f" [{item['special_note']}]"
        line += f" (cart_item_id: {item['cart_item_id']})"
        lines.append(line)
    lines.append(f"합계: {int(float(cart.get('total', 0)))}원")
    return "\n".join(lines)

@tool
def clear_cart() -> str:
    """장바구니를 전부 비운다."""
    session_id = get_session_id()
    try:
        _run(api_client.delete_cart(session_id))
    except Exception as e:
        return f"오류: 초기화 실패 — {e}"
    push_action({"type": "clear_cart"})
    return "장바구니를 비웠습니다."

@tool
def check_user_points(phone: str) -> str:
    """전화번호로 회원 포인트를 조회한다.
    Args:
        phone: 전화번호 (숫자만, 예: 01012345678)
    """
    try:
        data = _run(api_client.get_user_points(phone))
    except Exception as e:
        return f"오류: 포인트 조회 실패 — {e}"

    if data is None:
        return "등록된 회원 정보가 없습니다. 주문 후 포인트 적립이 가능합니다."

    return (
        f"안녕하세요! 현재 포인트는 {data['current_points']}점이며, "
        f"등급은 {data.get('tier', 'BASIC')}입니다."
    )

@tool
def navigate(screen: str) -> str:
    """화면을 이동한다. Args: screen: 'menu' | 'cart' | 'payment'"""
    push_action({"type": "navigate", "screen": screen})
    return f"{screen} 화면으로 이동"


@tool
def checkout(method: str | None = None) -> str:
    """결제를 진행한다. 장바구니가 비어 있으면 거부한다.

    Args:
        method: 결제 수단 ('card' | 'cash' | 'pay'). 생략 가능.
    """
    session_id = get_session_id()
    try:
        cart = _run(api_client.get_cart(session_id))
    except Exception as e:
        return f"오류: 장바구니 확인 실패 — {e}"

    if not cart.get("items"):
        return "담긴 메뉴가 없어요. 먼저 메뉴를 선택해 주세요."

    action: dict = {"type": "checkout"}
    if method:
        action["method"] = method
    push_action(action)
    return "결제 화면(장바구니)으로 이동합니다."


@tool
def confirm_order(user_phone: str | None = None) -> str:
    """장바구니의 메뉴로 주문을 확정하고 DB에 주문을 생성한다.

    Args:
        user_phone: 포인트 적립용 전화번호 (선택). 예: 01012345678
    """
    session_id = get_session_id()
    try:
        result = _run(api_client.create_order(session_id, user_phone))
    except Exception as e:
        return f"오류: 주문 생성 실패 — {e}"

    order_id = result.get("order_id", "")
    push_action({"type": "confirm_order", "order_id": order_id})
    return f"주문이 완료되었습니다! 주문 번호: {order_id}"


# ── ui_action: 화면 조작 범용 도구 ──────────────────────────────────────────
# action 별 허용 value 화이트리스트. None = value 불필요.
_UI_ACTION_SPEC: dict[str, set[str] | None] = {
    "update_modal": None,
    "order_type": {"dine-in", "takeout"},
    "select_category": {"recommended", "burger", "side", "drink"},
    "menu_page": {"next", "prev"},
    "open_item": None,
    "start_checkout": None,
    "points": {"yes", "no"},
    "points_phone": None,
    "payment_method": {"card", "cash", "pay"},
    "set_language": {"ko", "en", "zh", "ja"},
    "set_gesture": {"on", "off"},
    "set_camera": {"on", "off"},
}

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
def ui_action(
    action: str,
    value: str | None = None,
    item_type: str | None = None,
    field: str | None = None,
    field_value: str | None = None,
) -> str:
    """화면 UI를 조작하는 범용 도구. 현재 화면에 맞는 action만 호출한다.

    action 종류와 파라미터:
      - update_modal (field: qty|exclusion|side|drink, field_value: 변경값)
      - order_type (value: dine-in | takeout)
      - select_category (value: recommended|burger|side|drink)
      - menu_page (value: next | prev)
      - open_item (value: 메뉴 UUID)
      - start_checkout
      - points (value: yes | no)
      - points_phone (value: 전화번호)
      - payment_method (value: card | cash | pay)
      - set_language (value: ko | en | zh | ja)
      - set_gesture (value: on | off)
      - set_camera (value: on | off)
    """
    if action not in _UI_ACTION_SPEC:
        return f"오류: 지원하지 않는 action '{action}' 입니다."

    allowed = _UI_ACTION_SPEC[action]
    if allowed is not None:
        if value not in allowed:
            return f"오류: action '{action}' 의 value 는 {sorted(allowed)} 중 하나여야 합니다."
    elif action in ("open_item", "points_phone") and not value:
        return f"오류: action '{action}' 은 value 가 필요합니다."

    payload: dict = {"type": action}
    if action == "update_modal":
        _MODAL_FIELDS = {"qty", "exclusion", "side", "drink"}
        if not field or field not in _MODAL_FIELDS:
            return f"오류: update_modal 의 field 는 {sorted(_MODAL_FIELDS)} 중 하나여야 합니다."
        if not field_value:
            return "오류: update_modal 에는 field_value 가 필요합니다."
        payload["field"] = field
        payload["value"] = field_value
    elif action == "open_item":
        payload["menu_item_id"] = value
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


# 에이전트가 인식할 최종 도구 리스트 등록
ACTION_TOOLS = [
    list_menu,
    add_item,
    remove_item,
    update_item_options,
    get_cart_status,
    clear_cart,
    check_user_points,
    navigate,
    checkout,
    confirm_order,
    ui_action,
]