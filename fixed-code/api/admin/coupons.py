from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.db import get_session
from core.security import get_current_admin
from dao import coupon_dao
from schemas.coupon_schemas import CouponIn, CouponOut, UserCouponOut

router = APIRouter(
    prefix="/api/admin/coupons",
    tags=["admin-coupons"],
    dependencies=[Depends(get_current_admin)],
)


class IssueReq(BaseModel):
    phone: str


@router.get("", response_model=list[CouponOut])
async def get_coupons(db: AsyncSession = Depends(get_session)):
    return await coupon_dao.list_coupons(db)


@router.post("", response_model=CouponOut)
async def create_coupon(body: CouponIn, db: AsyncSession = Depends(get_session)):
    coupon = await coupon_dao.create_coupon(db, body)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.post("/{id}/issue", response_model=UserCouponOut)
async def issue_coupon(id: str, body: IssueReq, db: AsyncSession = Depends(get_session)):
    try:
        user_coupon = await coupon_dao.issue_coupon_to_user(db, id, body.phone)
        await db.commit()
        await db.refresh(user_coupon)
        return UserCouponOut(
            user_coupon_id=user_coupon.id,
            user_id=user_coupon.user_id,
            coupon_id=user_coupon.coupon_id,
            issued_at=user_coupon.issued_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
