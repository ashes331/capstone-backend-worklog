from pydantic import BaseModel
from decimal import Decimal

class OrderIn(BaseModel):
    session_id: str
    order_type: str = "TAKE_OUT"   # EAT_IN | TAKE_OUT
    phone: str | None = None        # 포인트 적립용 (비회원도 전화번호로 적립 가능)
    points_to_use: int = 0
    coupon_code: str | None = None

class OrderItemOut(BaseModel):
    menu_item_id: str
    name_ko: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    selected_options: list
    special_note: str | None

class OrderOut(BaseModel):
    order_id: str
    order_number: str
    order_type: str
    status: str                       # 1-A의 order.status
    subtotal: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    points_used: int
    points_earned: int
    items: list[OrderItemOut]


class OrderAdminOut(BaseModel):
    order_id: str
    order_number: str
    order_type: str
    status: str
    table_number: int | None
    subtotal: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    points_used: int
    points_earned: int
    created_at: str
    items: list[OrderItemOut]
    payment_status: str | None  # 연결된 Payment.status, 결제 전이면 None