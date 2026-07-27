from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import datetime
from core.models import Payment

async def create_payment(
    db: AsyncSession,
    order_id: str,
    method: str,
    amount: Decimal,
    pg_transaction_id: str | None = None,
    pg_provider: str | None = None,
) -> Payment:
    payment = Payment(
        order_id=order_id,
        method=method,
        amount=amount,
        pg_transaction_id=pg_transaction_id,
        pg_provider=pg_provider,
        status="SUCCESS",
        paid_at=datetime.utcnow(),
    )
    db.add(payment)
    await db.flush()
    return payment


async def get_payment_by_id(db: AsyncSession, payment_id: str) -> Payment | None:
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id).options(selectinload(Payment.order))
    )
    return result.scalar_one_or_none()


async def get_payment_by_order_id(db: AsyncSession, order_id: str) -> Payment | None:
    result = await db.execute(
        select(Payment)
        .where(Payment.order_id == order_id)
        .options(selectinload(Payment.order))
        .order_by(Payment.created_at.desc())
    )
    return result.scalars().first()


async def list_payments(db: AsyncSession, status: str | None = None) -> list[Payment]:
    query = select(Payment).options(selectinload(Payment.order))
    if status:
        query = query.where(Payment.status == status)
    result = await db.execute(query.order_by(Payment.created_at.desc()))
    return result.scalars().all()


async def mark_refunded(db: AsyncSession, payment_id: str, reason: str) -> Payment | None:
    """결제 상태를 REFUNDED로 변경하고 사유 기록 (DAO 규칙: flush만 호출)"""
    payment = await get_payment_by_id(db, payment_id)
    if payment:
        payment.status = "REFUNDED"
        payment.refunded_at = datetime.utcnow()
        payment.failure_reason = reason
        await db.flush()
    return payment