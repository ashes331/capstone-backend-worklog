from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PaymentIn(BaseModel):
    order_id: str
    method: str            # CARD | SAMSUNG_PAY | QR_PAY | CASH
    amount: Decimal
    pg_transaction_id: str | None = None
    pg_provider: str | None = None


class PaymentOut(BaseModel):
    payment_id: str
    order_id: str
    method: str
    amount: Decimal
    status: str
    paid_at: str | None


class PaymentAdminOut(BaseModel):
    payment_id: str
    order_id: str
    order_number: str
    method: str
    amount: float
    status: str  # PENDING | SUCCESS | FAILED | REFUNDED
    pg_transaction_id: str | None = None
    failure_reason: str | None = None
    paid_at: datetime | None = None
    refunded_at: datetime | None = None

    class Config:
        from_attributes = True


class RefundReq(BaseModel):
    reason: str
