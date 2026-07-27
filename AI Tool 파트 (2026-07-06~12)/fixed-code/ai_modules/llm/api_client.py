"""
DB API 연동 클라이언트
docs/AI_파트_작업명세.md 및 기존 스텁 구조를 통합하여 구현.
"""
from __future__ import annotations

import os
import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


async def get_menu() -> list[dict]:
    """
    GET /api/menu 
    기존 스텁의 메뉴 조회 함수를 명세서 규격에 맞게 구현.
    카테고리별로 분산된 menu_items를 하나의 리스트로 평탄화(Flatten)하여 반환합니다.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_BASE_URL}/api/menu?locale=ko")
        res.raise_for_status()
        data = res.json()
        
    items = []
    for category_items in data.get("menu_items", {}).values():
        items.extend(category_items)
    return items


async def fetch_menu_item_by_id(item_id: str) -> dict | None:
    """
    GET /api/menu/items/{id}
    특정 메뉴 상세 조회 (명세서 요구 기능 추가)
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_BASE_URL}/api/menu/items/{item_id}")
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()


async def add_cart_item(session_id: str, payload: dict) -> dict:
    """
    POST /api/cart/{session_id}/items
    장바구니 항목 추가.
    action_tools.py에서 패키징한 payload(menu_item_id, quantity, selected_options 등)를 그대로 전송합니다.
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_BASE_URL}/api/cart/{session_id}/items", json=payload)
        res.raise_for_status()
        return res.json()


async def patch_cart_item(session_id: str, cart_item_id: str, payload: dict) -> None:
    """
    PATCH /api/cart/{session_id}/items/{cart_item_id}
    장바구니 항목 수정 (명세서 요구 기능 추가)
    """
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{API_BASE_URL}/api/cart/{session_id}/items/{cart_item_id}", json=payload
        )
        res.raise_for_status()


async def remove_cart_item(session_id: str, cart_item_id: str) -> None:
    """
    DELETE /api/cart/{session_id}/items/{cart_item_id}
    장바구니에서 특정 항목 삭제.
    """
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{API_BASE_URL}/api/cart/{session_id}/items/{cart_item_id}")
        res.raise_for_status()


async def delete_cart(session_id: str) -> None:
    """
    DELETE /api/cart/{session_id}
    장바구니 전체 비우기 (명세서 요구 기능 추가)
    """
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{API_BASE_URL}/api/cart/{session_id}")
        res.raise_for_status()


async def get_cart(session_id: str) -> dict:
    """
    GET /api/cart/{session_id}
    현재 장바구니 상태 조회.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_BASE_URL}/api/cart/{session_id}")
        res.raise_for_status()
        return res.json()


async def get_user_points(phone: str) -> dict | None:
    """
    GET /api/user/points/{phone}
    회원 포인트 및 등급 조회.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_BASE_URL}/api/user/points/{phone}")
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()


async def create_order(session_id: str, user_phone: str = None) -> dict:
    """
    POST /api/orders
    기존 스텁에 있던 주문 생성 함수 (향후 checkout 툴 연동용 보존)
    """
    payload = {"session_id": session_id}
    if user_phone:
        payload["phone"] = user_phone
        
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_BASE_URL}/api/orders", json=payload)
        res.raise_for_status()
        return res.json()


# ── 지시서 1단계 수록 명세 함수명 매핑 호환용 별칭 (Alias) ──

async def fetch_menu_items() -> list[dict]:
    """GET /api/menu → items 목록 반환 (지시서 스펙 명칭 매핑)."""
    return await get_menu()

async def post_cart_add(session_id: str, payload: dict) -> dict:
    """POST /api/cart/{session_id}/items (지시서 스펙 명칭 매핑)."""
    return await add_cart_item(session_id, payload)

async def delete_cart_item(session_id: str, cart_item_id: str) -> None:
    """DELETE /api/cart/{session_id}/items/{cart_item_id} (지시서 스펙 명칭 매핑)."""
    await remove_cart_item(session_id, cart_item_id)