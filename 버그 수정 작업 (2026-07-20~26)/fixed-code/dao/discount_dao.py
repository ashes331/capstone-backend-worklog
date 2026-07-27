from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.core.models import Discount
from backend.schemas.coupon_schemas import DiscountIn


async def list_discounts(db: AsyncSession) -> list[Discount]:
    result = await db.execute(select(Discount))
    return result.scalars().all()


async def create_discount(db: AsyncSession, data: DiscountIn) -> Discount:
    discount = Discount(**data.model_dump())
    db.add(discount)
    await db.flush()
    return discount
