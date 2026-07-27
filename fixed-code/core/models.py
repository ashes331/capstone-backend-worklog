"""
DB 스키마 (스키마 명세서 13 테이블).

- 비회원 주문을 지원하기 위해 CARTS 는 session_id 로 식별.
- CART_ITEMS.special_note / ORDER_ITEMS.special_note 는 음성 비정형 요구사항 저장.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# --- USERS ---------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    accessibility_mode: Mapped[str] = mapped_column(
        SAEnum("NORMAL", "VOICE_GUIDE", "HIGH_CONTRAST", "LARGE_TEXT", name="accessibility_mode"),
        default="NORMAL",
    )
    preferred_language: Mapped[str] = mapped_column(
        SAEnum("ko", "en", "zh", "ja", name="preferred_language"), default="ko"
    )
    is_guest: Mapped[bool] = mapped_column(Boolean, default=True)
    current_points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# --- MEMBERSHIPS ---------------------------------------------------------
class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    tier: Mapped[str] = mapped_column(
        SAEnum("BASIC", "SILVER", "GOLD", name="membership_tier"), default="BASIC"
    )
    points: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# --- COUPONS -------------------------------------------------------------
class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    discount_type: Mapped[str] = mapped_column(
        SAEnum("CASH", "PERCENT", name="coupon_discount_type")
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    max_usage_count: Mapped[int] = mapped_column(Integer, default=0)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --- USER_COUPONS --------------------------------------------------------
class UserCoupon(Base):
    __tablename__ = "user_coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    coupon_id: Mapped[str] = mapped_column(String(36), ForeignKey("coupons.id"))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    coupon: Mapped["Coupon"] = relationship("Coupon")


# --- CATEGORIES ----------------------------------------------------------
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("categories.id"), nullable=True
    )
    name_ko: Mapped[str] = mapped_column(String(64))
    name_en: Mapped[str] = mapped_column(String(64))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)


# --- MENU_ITEMS ----------------------------------------------------------
class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"))
    name_ko: Mapped[str] = mapped_column(String(128))
    name_en: Mapped[str] = mapped_column(String(128))
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    options: Mapped[list["MenuOption"]] = relationship(
        "MenuOption", back_populates="menu_item", cascade="all,delete-orphan"
    )
    category: Mapped["Category"] = relationship("Category")


# --- MENU_OPTIONS --------------------------------------------------------
class MenuOption(Base):
    __tablename__ = "menu_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("menu_items.id"))
    name_ko: Mapped[str] = mapped_column(String(128))
    name_en: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    additional_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="options")


# --- DISCOUNTS -----------------------------------------------------------
class Discount(Base):
    __tablename__ = "discounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    menu_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("menu_items.id"), nullable=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("categories.id"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(
        SAEnum("MENU", "CATEGORY", "ALL", name="discount_target_type")
    )
    discount_type: Mapped[str] = mapped_column(
        SAEnum("CASH", "PERCENT", name="discount_value_type")
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    name_ko: Mapped[str] = mapped_column(String(128))
    name_en: Mapped[str] = mapped_column(String(128))
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    applicable_tier: Mapped[str] = mapped_column(
        SAEnum("ALL", "STUDENT", "SENIOR", "GOLD", name="discount_applicable_tier"),
        default="ALL",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# --- CARTS ---------------------------------------------------------------
class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        SAEnum("ACTIVE", "COMPLETED", "ABANDONED", name="cart_status"), default="ACTIVE"
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all,delete-orphan"
    )


# --- CART_ITEMS ----------------------------------------------------------
class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cart_id: Mapped[str] = mapped_column(String(36), ForeignKey("carts.id"))
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("menu_items.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    selected_options: Mapped[list | None] = mapped_column(JSON, default=list)
    # ★배리어프리: 음성에서 추출된 비정형 요구사항
    special_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem")


# --- ORDERS --------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    cart_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("carts.id"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(32), unique=True)
    order_type: Mapped[str] = mapped_column(
        SAEnum("EAT_IN", "TAKE_OUT", name="order_type"), default="TAKE_OUT"
    )
    table_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("RECEIVED", "COOKING", "READY", "COMPLETED", "CANCELLED", name="order_status"),
        default="RECEIVED",
    )
    # 환불 시 포인트·쿠폰을 정확히 원상복구하려면 이 주문에 어떤 쿠폰을 썼는지가 남아있어야 한다.
    user_coupon_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user_coupons.id"), nullable=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    points_used: Mapped[int] = mapped_column(Integer, default=0)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all,delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="order")


# --- ORDER_ITEMS ---------------------------------------------------------
class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("menu_items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    selected_options: Mapped[list | None] = mapped_column(JSON, default=list)
    special_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem")


# --- PAYMENTS ------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    method: Mapped[str] = mapped_column(
        SAEnum("CARD", "SAMSUNG_PAY", "QR_PAY", "CASH", name="payment_method")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pg_transaction_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    pg_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("PENDING", "SUCCESS", "FAILED", "REFUNDED", name="payment_status"),
        default="PENDING",
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order: Mapped["Order"] = relationship("Order", back_populates="payments")


# --- ADMIN_USERS -----------------------------------------------------------
class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(
        SAEnum("OWNER", "STAFF", name="admin_role"), default="STAFF"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
