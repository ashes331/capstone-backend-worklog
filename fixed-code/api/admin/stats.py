from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session
from core.security import get_current_admin
from dao import stats_dao
from schemas.stats_schemas import (
    StatsSummaryOut,
    SalesSeriesOut,
    SalesPointOut,
    PopularItemOut,
)

router = APIRouter(
    prefix="/api/admin/stats",
    tags=["admin-stats"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/summary", response_model=StatsSummaryOut)
async def get_summary(db: AsyncSession = Depends(get_session)):
    """오늘의 매출 요약 통계"""
    data = await stats_dao.get_today_summary(db)
    return StatsSummaryOut(**data)


@router.get("/sales", response_model=SalesSeriesOut)
async def get_sales(range: str = "7d", db: AsyncSession = Depends(get_session)):
    """일자별 매출 추이 (기본 7일)"""
    days = 30 if range == "30d" else 7
    series = await stats_dao.get_sales_series(db, days=days)
    return SalesSeriesOut(
        range=range,
        data=[SalesPointOut(**point) for point in series]
    )


@router.get("/popular-items", response_model=list[PopularItemOut])
async def get_popular_items(range: str = "7d", db: AsyncSession = Depends(get_session)):
    """인기 메뉴 랭킹"""
    days = 30 if range == "30d" else 7
    items = await stats_dao.get_popular_items(db, days=days)
    return [PopularItemOut(**item) for item in items]
