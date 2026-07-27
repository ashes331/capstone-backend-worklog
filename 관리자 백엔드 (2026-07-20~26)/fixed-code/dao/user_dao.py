import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.models import User, Membership, UserCoupon, Coupon

logger = logging.getLogger(__name__)

async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    return result.scalar_one_or_none()

async def get_membership(db: AsyncSession, user_id: str) -> Membership | None:
    result = await db.execute(
        select(Membership).where(Membership.user_id == user_id)
    )
    return result.scalar_one_or_none()

async def get_unused_coupons(db: AsyncSession, user_id: str) -> list[UserCoupon]:
    result = await db.execute(
        select(UserCoupon)
        .where(UserCoupon.user_id == user_id)
        .where(UserCoupon.is_used == False)
    )
    return result.scalars().all()

async def get_coupon_by_code(db: AsyncSession, code: str) -> Coupon | None:
    result = await db.execute(
        select(Coupon)
        .where(Coupon.code == code)
        .where(Coupon.is_active == True)
    )
    return result.scalar_one_or_none()


# --- 관리자용 (Module G) -----------------------------------------------------

async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def search_users(db: AsyncSession, phone: str | None = None) -> list[User]:
    query = select(User).order_by(User.created_at.desc())
    if phone:
        query = query.where(User.phone_number.contains(phone))
    result = await db.execute(query)
    return result.scalars().all()


async def get_all_user_coupons(db: AsyncSession, user_id: str) -> list[UserCoupon]:
    result = await db.execute(
        select(UserCoupon).where(UserCoupon.user_id == user_id)
    )
    return result.scalars().all()


async def adjust_points(db: AsyncSession, user_id: str, delta: int, reason: str = "") -> User | None:
    """포인트 수동 증감. reason은 서버 로그에 남긴다."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.current_points += delta
    await db.flush()
    logger.info(
        "admin points adjustment: user_id=%s delta=%s reason=%s new_balance=%s",
        user_id, delta, reason, user.current_points,
    )
    return user

# --- Module C: 쿠폰 관련 DAO ---

async def get_user_coupon_by_code(db: AsyncSession, user_id: str, code: str) -> UserCoupon | None:
    """쿠폰 코드로 미사용 유저 쿠폰 조회"""
    result = await db.execute(
        select(UserCoupon)
        .join(Coupon, UserCoupon.coupon_id == Coupon.id)
        .where(
            UserCoupon.user_id == user_id,
            Coupon.code == code,
            UserCoupon.is_used == False,
        )
        .options(selectinload(UserCoupon.coupon))
    )
    return result.scalar_one_or_none()


async def mark_coupon_used(db: AsyncSession, user_coupon_id: str) -> None:
    """쿠폰 사용 완료 처리. is_used=True, used_at=now(), coupons.used_count += 1."""
    user_coupon = await db.get(UserCoupon, user_coupon_id)
    if user_coupon:
        user_coupon.is_used = True
        user_coupon.used_at = datetime.utcnow()
        coupon = await db.get(Coupon, user_coupon.coupon_id)
        if coupon:
            coupon.used_count += 1
        await db.flush()


async def restore_coupon(db: AsyncSession, user_coupon_id: str) -> None:
    """환불 시 쿠폰 복구. mark_coupon_used의 반대 동작."""
    user_coupon = await db.get(UserCoupon, user_coupon_id)
    if user_coupon:
        user_coupon.is_used = False
        user_coupon.used_at = None
        coupon = await db.get(Coupon, user_coupon.coupon_id)
        if coupon:
            coupon.used_count -= 1
        await db.flush()