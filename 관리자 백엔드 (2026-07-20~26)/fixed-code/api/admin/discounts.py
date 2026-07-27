from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session
from core.security import get_current_admin
from dao import discount_dao
from schemas.coupon_schemas import DiscountIn, DiscountOut

router = APIRouter(
    prefix="/api/admin/discounts",
    tags=["admin-discounts"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[DiscountOut])
async def get_discounts(db: AsyncSession = Depends(get_session)):
    return await discount_dao.list_discounts(db)


@router.post("", response_model=DiscountOut)
async def create_discount(body: DiscountIn, db: AsyncSession = Depends(get_session)):
    # target_type 검증 규칙 적용
    if body.target_type == "MENU" and not body.menu_item_id:
        raise HTTPException(status_code=400, detail="MENU 할인 시 menu_item_id는 필수입니다.")
    if body.target_type == "CATEGORY" and not body.category_id:
        raise HTTPException(status_code=400, detail="CATEGORY 할인 시 category_id는 필수입니다.")

    discount = await discount_dao.create_discount(db, body)
    await db.commit()
    await db.refresh(discount)
    return discount
