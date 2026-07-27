from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session
from core.models import Order, OrderItem
from schemas.order_schemas import OrderIn, OrderOut, OrderItemOut
from dao import user_dao, order_dao, cart_dao

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _to_order_item_out(item: OrderItem) -> OrderItemOut:
    return OrderItemOut(
        menu_item_id=item.menu_item_id,
        name_ko=item.menu_item.name_ko if item.menu_item else "",
        quantity=item.quantity,
        unit_price=item.unit_price,
        total_price=item.total_price,
        selected_options=item.selected_options or [],
        special_note=item.special_note,
    )


@router.post("", response_model=OrderOut)
async def create_order(body: OrderIn, db: AsyncSession = Depends(get_session)):
    """주문 생성 API
    - items 직렬화 버그 수정
    - 회원 포인트 적립 및 차감 실제 반영
    - 쿠폰 할인 적용 및 사용 처리
    """
    # 1. 장바구니 조회 및 검증
    cart = await cart_dao.get_cart_with_items(db, body.session_id)
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="장바구니가 비어있거나 존재하지 않습니다.")

    # 2. 금액 계산 (Subtotal)
    subtotal = sum(item.unit_price * item.quantity for item in cart.items)
    discount_amount = Decimal("0")
    user_coupon_id = None
    user = None

    # 회원 정보 조회 (전화번호가 제공된 경우)
    if body.phone:
        user = await user_dao.get_user_by_phone(db, body.phone)

    # 3. 쿠폰 적용 로직 (회원 전용)
    if body.coupon_code:
        if not user:
            raise HTTPException(status_code=400, detail="쿠폰은 회원만 사용할 수 있습니다.")

        user_coupon = await user_dao.get_user_coupon_by_code(db, user.id, body.coupon_code)
        if not user_coupon:
            raise HTTPException(status_code=400, detail="유효하지 않거나 이미 사용된 쿠폰입니다.")

        coupon = user_coupon.coupon
        if not coupon.is_active:
            raise HTTPException(status_code=400, detail="비활성화된 쿠폰입니다.")

        if subtotal < coupon.min_order_amount:
            raise HTTPException(
                status_code=400,
                detail=f"최소 주문 금액({coupon.min_order_amount}원)을 충족하지 못했습니다."
            )

        # 할인 금액 계산
        if coupon.discount_type == "PERCENT":
            discount_amount = subtotal * (coupon.discount_value / Decimal("100"))
        else:  # CASH
            discount_amount = coupon.discount_value

        user_coupon_id = user_coupon.id

    # 4. 포인트 사용 및 적립 계산 (기본 1% 적립)
    points_to_use = body.points_to_use or 0
    if points_to_use > 0:
        if not user:
            raise HTTPException(status_code=400, detail="포인트 사용은 회원만 가능합니다.")
        if user.current_points < points_to_use:
            raise HTTPException(status_code=400, detail="보유 포인트가 부족합니다.")

    final_amount = max(Decimal("0"), subtotal - discount_amount - Decimal(points_to_use))
    points_earned = int(final_amount * Decimal("0.01"))  # 결제금액의 1% 적립

    # 5. 주문(Order) 객체 생성
    order_number = f"ORD-{int(datetime.now().timestamp())}"
    order = Order(
        user_id=user.id if user else None,
        cart_id=cart.id,
        order_number=order_number,
        order_type=body.order_type,
        status="RECEIVED",  # 기본 상태: 접수됨
        user_coupon_id=user_coupon_id,
        subtotal=subtotal,
        discount_amount=discount_amount,
        final_amount=final_amount,
        points_used=points_to_use,
        points_earned=points_earned,
    )
    db.add(order)
    await db.flush()

    # 6. 주문 항목(OrderItem) 복사
    order_items = []
    for cart_item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=cart_item.menu_item_id,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            total_price=cart_item.unit_price * cart_item.quantity,
            selected_options=cart_item.selected_options,
            special_note=cart_item.special_note,
        )
        order_item.menu_item = cart_item.menu_item
        db.add(order_item)
        order_items.append(order_item)

    # 7. 쿠폰 사용 처리 및 포인트 차감/적립 반영
    if user_coupon_id:
        await user_dao.mark_coupon_used(db, user_coupon_id)

    if user:
        # 사용 포인트 차감 (-) 및 적립 포인트 반영 (+)
        net_point_change = points_earned - points_to_use
        await user_dao.adjust_points(db, user.id, net_point_change)

    # 8. 장바구니 완료 처리 및 DB 최종 커밋
    cart.status = "COMPLETED"
    await db.commit()
    await db.refresh(order)

    # 9. 응답 데이터 직렬화 (items 목록 채우기)
    items_out = [_to_order_item_out(item) for item in order_items]

    return OrderOut(
        order_id=order.id,
        order_number=order.order_number,
        order_type=order.order_type,
        status=order.status,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        final_amount=order.final_amount,
        points_used=order.points_used,
        points_earned=order.points_earned,
        items=items_out,
    )


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, db: AsyncSession = Depends(get_session)):
    """주문 단건 조회 API (실제 status 및 items 반환)"""
    order = await order_dao.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    items_out = [_to_order_item_out(item) for item in order.items]

    return OrderOut(
        order_id=order.id,
        order_number=order.order_number,
        order_type=order.order_type,
        status=order.status,  # ★ 하드코딩 "completed" 대신 실제 order.status 반환!
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        final_amount=order.final_amount,
        points_used=order.points_used,
        points_earned=order.points_earned,
        items=items_out,
    )
