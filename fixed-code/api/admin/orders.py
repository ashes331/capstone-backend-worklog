from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session
from core.security import get_current_admin
from dao import order_dao
from schemas.order_schemas import OrderAdminOut, OrderItemOut

# 명세서 규칙: 상태 전이는 앞으로만 가능 (CANCELLED는 COMPLETED 제외하고 항상 허용)
_ORDER_STEPS = ["RECEIVED", "COOKING", "READY", "COMPLETED"]

def _is_valid_transition(current: str, new: str) -> bool:
    if new == "CANCELLED":
        return current != "COMPLETED"
    if current == "CANCELLED":
        return False
    if current not in _ORDER_STEPS or new not in _ORDER_STEPS:
        return False
    return _ORDER_STEPS.index(new) > _ORDER_STEPS.index(current)


router = APIRouter(
    prefix="/api/admin/orders",
    tags=["admin-orders"],
    dependencies=[Depends(get_current_admin)],
)


def _to_order_admin_out(order) -> OrderAdminOut:
    payment_status = order.payments[-1].status if order.payments else None
    items_out = [
        OrderItemOut(
            menu_item_id=item.menu_item_id,
            name_ko=item.menu_item.name_ko if item.menu_item else "",
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            selected_options=item.selected_options or [],
            special_note=item.special_note,
        )
        for item in order.items
    ]
    return OrderAdminOut(
        order_id=order.id,
        order_number=order.order_number,
        order_type=order.order_type,
        status=order.status,
        table_number=order.table_number,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        final_amount=order.final_amount,
        points_used=order.points_used,
        points_earned=order.points_earned,
        items=items_out,
        created_at=order.created_at.isoformat(),
        payment_status=payment_status,
    )


@router.get("", response_model=list[OrderAdminOut])
async def get_admin_orders(
    status: str | None = None,
    order_type: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """관리자 주문 목록 조회"""
    orders = await order_dao.list_orders(db, status=status, order_type=order_type)
    return [_to_order_admin_out(order) for order in orders]


@router.patch("/{order_id}/status", response_model=OrderAdminOut)
async def update_status(
    order_id: str,
    status: str,
    db: AsyncSession = Depends(get_session),
):
    """관리자 주문 상태 변경"""
    target_order = await order_dao.get_order_by_id(db, order_id)
    if not target_order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    # 상태 전이 검증 (역방향 금지)
    if not _is_valid_transition(target_order.status, status):
        raise HTTPException(
            status_code=400,
            detail=f"'{target_order.status}'에서 '{status}'(으)로 상태를 변경할 수 없습니다."
        )

    await order_dao.update_order_status(db, order_id, status)
    await db.commit()

    updated_order = await order_dao.get_order_by_id(db, order_id)
    return _to_order_admin_out(updated_order)
