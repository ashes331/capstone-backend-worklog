from datetime import date, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.models import Order, OrderItem, MenuItem


async def get_today_summary(db: AsyncSession) -> dict:
    """오늘 매출 합계, 주문 건수, 평균 객단가"""
    today = date.today()
    result = await db.execute(
        select(Order).where(
            Order.status == "COMPLETED",
            func.date(Order.created_at) == today,
        )
    )
    orders = result.scalars().all()

    order_count = len(orders)
    today_sales = sum(float(o.final_amount) for o in orders)
    avg_order_value = (today_sales / order_count) if order_count > 0 else 0.0

    return {
        "today_sales": today_sales,
        "order_count": order_count,
        "avg_order_value": avg_order_value,
    }


async def get_sales_series(db: AsyncSession, days: int) -> list[dict]:
    """최근 N일간 일자별 매출 추이"""
    start_date = date.today() - timedelta(days=days)
    result = await db.execute(
        select(Order).where(
            Order.status == "COMPLETED",
            func.date(Order.created_at) >= start_date,
        )
    )
    orders = result.scalars().all()

    daily_map = {}
    for i in range(days + 1):
        d_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_map[d_str] = {"sales": 0.0, "order_count": 0}

    for o in orders:
        d_str = o.created_at.strftime("%Y-%m-%d")
        if d_str in daily_map:
            daily_map[d_str]["sales"] += float(o.final_amount)
            daily_map[d_str]["order_count"] += 1

    return [
        {"date": d_str, "sales": data["sales"], "order_count": data["order_count"]}
        for d_str, data in sorted(daily_map.items())
    ]


async def get_popular_items(db: AsyncSession, days: int, limit: int = 5) -> list[dict]:
    """인기 메뉴 랭킹 (판매 수량 및 매출액 기준)"""
    start_date = date.today() - timedelta(days=days)
    result = await db.execute(
        select(
            OrderItem.menu_item_id,
            MenuItem.name_ko,
            func.sum(OrderItem.quantity).label("quantity_sold"),
            func.sum(OrderItem.total_price).label("revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
        .where(
            Order.status == "COMPLETED",
            func.date(Order.created_at) >= start_date,
        )
        .group_by(OrderItem.menu_item_id, MenuItem.name_ko)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )

    return [
        {
            "menu_item_id": r.menu_item_id,
            "name_ko": r.name_ko,
            "quantity_sold": int(r.quantity_sold),
            "revenue": float(r.revenue),
        }
        for r in result.all()
    ]
