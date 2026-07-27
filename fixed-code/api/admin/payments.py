from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session
from core.security import get_current_admin
from dao import payment_dao, order_dao, user_dao
from schemas.payment_schemas import PaymentAdminOut, RefundReq

router = APIRouter(
    prefix="/api/admin/payments",
    tags=["admin-payments"],
    dependencies=[Depends(get_current_admin)],
)


def _to_payment_admin_out(p) -> PaymentAdminOut:
    return PaymentAdminOut(
        payment_id=p.id,
        order_id=p.order_id,
        order_number=p.order.order_number if p.order else "",
        method=p.method,
        amount=p.amount,
        status=p.status,
        pg_transaction_id=p.pg_transaction_id,
        failure_reason=p.failure_reason,
        paid_at=p.paid_at,
        refunded_at=p.refunded_at,
    )


@router.get("", response_model=list[PaymentAdminOut])
async def get_payments(status: str | None = None, db: AsyncSession = Depends(get_session)):
    payments = await payment_dao.list_payments(db, status=status)
    return [_to_payment_admin_out(p) for p in payments]


@router.post("/{id}/refund", response_model=PaymentAdminOut)
async def refund_payment(id: str, body: RefundReq, db: AsyncSession = Depends(get_session)):
    """결제 환불 API:
    1. 포인트 원상복구 (적립 회수, 사용분 반환)
    2. 사용된 쿠폰 복구 (is_used=False)
    3. 결제 상태 -> REFUNDED, 주문 상태 -> CANCELLED
    """
    payment = await payment_dao.get_payment_by_id(db, id)
    if not payment:
        raise HTTPException(status_code=404, detail="결제 내역을 찾을 수 없습니다.")
    if payment.status == "REFUNDED":
        raise HTTPException(status_code=409, detail="이미 환불된 결제입니다.")

    order = await order_dao.get_order_by_id(db, payment.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="연결된 주문 내역을 찾을 수 없습니다.")

    # 1. 포인트 원상복구: (적립분 - 사용분)의 반대값으로 역산
    if order.user_id:
        net_point_change = order.points_earned - order.points_used
        await user_dao.adjust_points(db, order.user_id, -net_point_change)

    # 2. 쿠폰 원상복구
    if order.user_coupon_id:
        await user_dao.restore_coupon(db, order.user_coupon_id)

    # 3. 결제 상태 REFUNDED 및 주문 상태 CANCELLED로 변경
    #    ★ Module E의 _is_valid_transition 검증을 거치지 않고 직접 호출 (완료된 주문도 환불 가능해야 함)
    await payment_dao.mark_refunded(db, id, body.reason)
    await order_dao.update_order_status(db, order.id, "CANCELLED")

    await db.commit()

    updated_payment = await payment_dao.get_payment_by_id(db, id)
    return _to_payment_admin_out(updated_payment)
