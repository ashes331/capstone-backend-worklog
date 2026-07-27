"""
SQLAlchemy 비동기 엔진 / 세션 / Base.
DB 접속 정보는 .env의 개별 환경변수로 관리한다.
  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
단일 URL이 필요하면 DATABASE_URL로 오버라이드 가능.
"""
import os
from dotenv import load_dotenv

# 프로젝트 루트 경로의 .env 파일을 확실하게 로드합니다.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_project_root, ".env"))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


def _build_database_url() -> str:
    # DATABASE_URL이 직접 지정된 경우 우선 사용
    if url := os.getenv("DATABASE_URL"):
        return url

    host     = os.getenv("DB_HOST",     "localhost")
    port     = os.getenv("DB_PORT",     "3306")
    user     = os.getenv("DB_USER",     "root")
    password = os.getenv("DB_PASSWORD", "")
    name     = os.getenv("DB_NAME",     "kiosk_db")

    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


DATABASE_URL = _build_database_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,   # idle 상태에서 끊긴 커넥션 자동 감지
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    """FastAPI Depends용 세션 컨텍스트."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """앱 시작 시 테이블 생성 + 메뉴 시드."""
    from . import models  # noqa: F401
    from .seed import seed_menu

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await seed_menu(session)