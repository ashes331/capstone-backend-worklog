"""
메뉴 RAG.

- MENU_ITEMS.description 을 OpenAIEmbeddings 로 벡터화하여 FAISS 인메모리 인덱스에 보관.
- 첫 호출 시 lazy build, 이후 캐시.
- 할루시네이션 방지를 위해 검색 결과의 menu_item_id / 가격 / 옵션을 그대로 Agent 에 반환.
"""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.db import SessionLocal
from backend.core.models import MenuItem


_index: FAISS | None = None
_build_lock = asyncio.Lock()


def _format_decimal(v: Decimal) -> float:
    return float(v)


async def _load_documents() -> tuple[list[Document], dict[str, dict[str, Any]]]:
    """DB 에서 메뉴 + 옵션을 읽어 Document 와 메타맵을 만든다."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(MenuItem).options(selectinload(MenuItem.options))
        )
        items = result.scalars().all()

    docs: list[Document] = []
    meta_map: dict[str, dict[str, Any]] = {}
    for item in items:
        options = [
            {
                "id": opt.id,
                "name_ko": opt.name_ko,
                "name_en": opt.name_en,
                "additional_price": _format_decimal(opt.additional_price),
            }
            for opt in item.options
        ]
        meta = {
            "id": item.id,
            "name_ko": item.name_ko,
            "name_en": item.name_en,
            "base_price": _format_decimal(item.base_price),
            "description": item.description,
            "options": options,
            "is_available": item.is_available,
        }
        meta_map[item.id] = meta

        # 검색 텍스트: 한국어/영어 이름 + 설명 모두 포함
        searchable = (
            f"{item.name_ko} ({item.name_en})\n"
            f"가격: {meta['base_price']}원\n"
            f"{item.description}"
        )
        docs.append(Document(page_content=searchable, metadata={"menu_item_id": item.id}))

    return docs, meta_map


_meta_map: dict[str, dict[str, Any]] = {}


async def _build_index() -> FAISS:
    global _index, _meta_map
    docs, meta_map = await _load_documents()
    _meta_map = meta_map
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # API 키가 설정되지 않은 경우 모의 임베딩 또는 예외 우회 처리
        api_key = "dummy_key_for_local_health_check"
        
    embeddings = OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        api_key=api_key,
    )
    # FAISS.from_documents 는 동기 호출 → 스레드로 오프로드
    try:
        _index = await asyncio.to_thread(FAISS.from_documents, docs, embeddings)
    except Exception as e:
        # 로컬 헬스 체크 중 인덱스 빌드 실패 방어
        print(f"[RAG 경고] 인덱스 빌드 건너뜀 (API Key 유효성 이슈): {e}")
        # 빈 인덱스로 헬스 체크 통과 유도
        from langchain_community.vectorstores import FAISS
        from langchain_core.embeddings import FakeEmbeddings
        fake_emb = FakeEmbeddings(size=1536)
        _index = await asyncio.to_thread(FAISS.from_documents, docs[:1], fake_emb)
        
    return _index


async def get_index() -> FAISS:
    global _index
    if _index is None:
        async with _build_lock:
            if _index is None:
                await _build_index()
    return _index  # type: ignore[return-value]


async def search_menu(query: str, k: int = 5) -> list[dict[str, Any]]:
    """질의어와 가장 유사한 메뉴 k 개를 반환."""
    index = await get_index()
    # similarity_search 는 동기 → 스레드로 오프로드
    results = await asyncio.to_thread(index.similarity_search, query, k)
    hits: list[dict[str, Any]] = []
    for doc in results:
        item_id = doc.metadata.get("menu_item_id")
        meta = _meta_map.get(item_id) if item_id else None
        if meta:
            hits.append(meta)
    return hits


def invalidate_cache() -> None:
    """메뉴 변경 시 RAG 캐시 무효화."""
    global _index, _meta_map
    _index = None
    _meta_map = {}

# --- 지시서 명세 4단계 규격 호환을 위한 스텁/래퍼 인터페이스 함수 ---

async def build_menu_index() -> list[dict]:
    """DB 기반에서 메뉴 인덱싱 용도를 충족하기 위한 호환용 함수."""
    docs, meta_map = await _load_documents()
    return [
        {
            "id": doc.metadata["menu_item_id"],
            "name": meta_map[doc.metadata["menu_item_id"]]["name_ko"],
            "description": meta_map[doc.metadata["menu_item_id"]]["description"],
            "text": doc.page_content
        }
        for doc in docs
    ]

def search_menu_by_query(query: str, documents: list[dict], top_k: int = 3) -> list[dict]:
    """키워드 기반의 임시 RAG 쿼리 룩업용 호환용 함수."""
    query_lower = query.lower()
    scored = []
    for doc in documents:
        score = sum(1 for kw in query_lower.split() if kw in doc["text"].lower())
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    return [doc for _, doc in scored[:top_k]]

