"""
LLM Agent 엔드포인트.

POST /ai_modules/llm
- Body: { "session_id": "...", "input": "...텍스트 (STT 결과)...", "cart": [...], "screen": "..." }
- 응답: { "output": "...", "actions": [...], "intermediate_steps": [...] }

POST /ai_modules/llm/stream
- SSE: data:{"token":"..."} ... data:{"action":{...}} ... data:{"done":true,"output":"..."}
"""
from __future__ import annotations

from ai_modules.llm.action_context import set_session_id

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ai_modules.llm.memory import reset_memory
from core.llm_service import run_agent, run_agent_stream


router = APIRouter(prefix="/ai_modules", tags=["llm"])


class CartLine(BaseModel):
    cart_id: float | int | None = None
    menu_id: int
    name: str | None = None
    item_type: str = "single"
    quantity: int = 1
    unit_price: float = 0
    exclusion: str = "없음"
    side: str | None = None
    drink: str | None = None


class ModalState(BaseModel):
    menu_id:   int
    name:      str | None = None
    item_type: str = "single"
    qty:       int = 1
    exclusion: str | None = None
    side:      str | None = None
    drink:     str | None = None

class LLMRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    input: str = Field(..., min_length=1, max_length=4000)
    language: str | None = Field(None, max_length=10)  # STT 감지 언어 코드 (ko/en/zh/ja)
    screen: str | None = None           # 현재 화면 (menu/cart 등)
    order_type: str | None = None       # 매장/포장 선택 여부 (dine-in|takeout|None)
    cart: list[CartLine] = []           # 현재 장바구니 스냅샷
    modal_state: ModalState | None = None  # 현재 열린 팝업 선택 상태


@router.post("/llm")
async def llm(req: LLMRequest):
    try:
        # 에이전트 실행 직전 세션 ID 주입
        set_session_id(req.session_id)

        cart_dicts = [c.model_dump() for c in req.cart]
        return await run_agent(
            req.session_id,
            req.input,
            language=req.language,
            cart=cart_dicts,
            screen=req.screen,
            order_type=req.order_type,
            modal_state=req.modal_state.model_dump() if req.modal_state else None,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"LLM 처리 실패: {e}")


@router.post("/llm/stream")
async def llm_stream(req: LLMRequest):
    """SSE 스트리밍 엔드포인트 — 토큰 단위로 text/event-stream 반환."""
    try:
        # 스트리밍 에이전트 실행 직전에도 세션 ID 주입
        set_session_id(req.session_id)

        cart_dicts = [c.model_dump() for c in req.cart]
        return StreamingResponse(
            run_agent_stream(
                req.session_id,
                req.input,
                language=req.language,
                cart=cart_dicts,
                modal_state=req.modal_state.model_dump() if req.modal_state else None,
                screen=req.screen,
                order_type=req.order_type,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"LLM 스트리밍 실패: {e}")


@router.post("/llm/reset")
async def llm_reset(session_id: str):
    await reset_memory(session_id)
    return {"ok": True, "session_id": session_id}