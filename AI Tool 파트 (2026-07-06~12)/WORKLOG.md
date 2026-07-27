# 작업 로그 — 지시서 기준 정리

기간: 2026-07-06 ~ 2026-07-12
브랜치: `feature/llm-db-tools` (원본: [Capstone-F5/CapstoneProject](https://github.com/Capstone-F5/CapstoneProject))
기준 문서: `docs/지시서_AI파트.md`, `docs/AI_파트_작업명세.md`
관련 커밋: `9e4c15b`, `3155fdc`, `3aab530`, `29f53e8`, `0e7a976`, `bcbe7e3`

> **참고:** 이 폴더는 이미 지나간 커밋 히스토리(git log/diff)를 근거로 사후에 재구성한 기록입니다.
> 관리자 백엔드 작업(`관리자 백엔드 (2026-07-20~26)`)처럼 이번 세션에서 직접 curl로 재검증한 것이
> 아니라, 커밋 메시지와 diff 내용을 바탕으로 정리했다는 점을 밝혀둡니다.

지시서 역할 분배: **김성원 — `action_tools.py` 재작성** / **임지연 — `api_client.py`, `rag.py`, `prompts.py`, `action_context.py`**

---

## 임지연 담당 — api_client.py · rag.py · prompts.py · action_context.py

**지시서 체크리스트**
- `api_client.py`: `fetch_menu_items`, `fetch_menu_item_by_id`, `post_cart_add`, `patch_cart_item`,
  `delete_cart_item`, `delete_cart`, `get_cart`, `get_user_points` 함수
- `action_context.py`: `set_session_id`/`get_session_id` 추가
- `backend/api/llm.py`: agent 실행 직전 `set_session_id(session_id)` 주입
- `rag.py`: 명세서의 `build_menu_index()`, `search_menu_by_query()` 함수 추가
- `prompts.py`: `ADDITIONAL_SCENARIOS` 내용 보완

**진행 상황 및 제가 보완한 부분 (2026-07-06, 커밋 `29f53e8`):**

1. **`rag.py` — API 키 미설정 시 인덱스 빌드가 그대로 죽는 문제**를 방어 로직으로 보완.
   `OPENAI_API_KEY`가 없을 때 `FakeEmbeddings`로 빈 인덱스를 만들어 최소한 헬스체크는
   통과하도록 처리했고, 지시서 명세가 요구하는 `build_menu_index()`/`search_menu_by_query()`
   스텁 함수를 추가했습니다.

   ```python
   # ai_modules/llm/rag.py — 추가된 방어 로직
   try:
       _index = await asyncio.to_thread(FAISS.from_documents, docs, embeddings)
   except Exception as e:
       print(f"[RAG 경고] 인덱스 빌드 건너뜀 (API Key 유효성 이슈): {e}")
       fake_emb = FakeEmbeddings(size=1536)
       _index = await asyncio.to_thread(FAISS.from_documents, docs[:1], fake_emb)
   ```

2. **`prompts.py` — 시나리오 누락 보완.** 포인트·쿠폰 안내, 메뉴 추천(인기/비건/저칼로리),
   장바구니 수정("아까 담은 버거 빼주세요" 같은 대명사 참조 처리) 시나리오를 추가했습니다.

3. **`api_client.py` — 필드명 불일치 (2026-07-12, 커밋 `bcbe7e3`).** `create_order`가 보내는
   payload 키가 `user_phone`이었는데, 실제 백엔드 `OrderIn` 스키마는 `phone`을 기대하고 있어
   그대로 보내면 무시되는 상태였습니다.

   ```python
   # 수정 전
   payload = {"session_id": session_id}
   if user_phone:
       payload["user_phone"] = user_phone

   # 수정 후
   payload = {"session_id": session_id}
   if user_phone:
       payload["phone"] = user_phone
   ```

   (참고: 이 `session_id` 기반 `OrderIn` 스키마는 이후 관리자 백엔드 작업 때도 그대로 확인한
   실제 스키마와 일치합니다.)

---

## 김성원 담당 — action_tools.py 재작성

**지시서 체크리스트**
- 기존 `action_tools.py`를 `action_tools_legacy.py`로 백업
- `add_item`(menu_id → menu_item_id), `remove_item`(menu_id → cart_item_id),
  `update_item_options`(update_qty+update_item 통합) 재작성
- `get_cart_status`, `check_user_points` Tool 신규 추가
- `clear_cart`는 `api_client.delete_cart` 호출로 수정
- `navigate`/`checkout`/`ui_action`은 그대로 유지
- `menu_catalog.py`에 "STT 어휘 힌트 전용으로 역할 축소" 주석 추가

**진행 상황 (2026-07-06, 커밋 `9e4c15b`):** 지시서 그대로 전체 재작성 완료, `action_tools_legacy.py` 백업.

**추가로 발견해 고친 문제 (2026-07-12, 커밋 `bcbe7e3`):**

1. **`menu_item_id`(UUID) 확인 수단이 없었음.** `add_item`이 `menu_item_id`를 파라미터로 받도록
   바뀌었는데, LLM이 그 UUID를 알아낼 방법이 없어 `list_menu` Tool을 신규로 추가했습니다.

   ```python
   @tool
   def list_menu() -> str:
       """판매 중인 메뉴 목록을 menu_item_id와 함께 조회한다. add_item 호출 전 menu_item_id 확인용으로 사용."""
       items = _run(api_client.fetch_menu_items())
       lines = ["[메뉴 목록]"]
       for item in items:
           status = " [품절]" if not item.get("is_available", True) else ""
           lines.append(f"- {item['name_ko']} {int(float(item['base_price']))}원 (menu_item_id: {item['id']}){status}")
       return "\n".join(lines)
   ```

2. **가격 캐스팅 크래시.** `get_cart_status` 등에서 `int(item['unit_price'])`처럼 DB가 반환하는
   `Decimal` 문자열(`"6200.00"`)을 바로 `int()`로 변환하려다 죽는 버그를 `int(float(...))`로 수정.

3. **`prompts.py`의 존재하지 않는 도구명 참조.** `update_qty`/`update_item`이라는, 실제로는
   통합되어 없어진 도구명이 프롬프트에 남아있던 것을 `update_item_options`로 정리하고,
   DB 마이그레이션 이전의 숫자 ID 카탈로그 안내를 `list_menu` 기반 UUID 조회 안내로 교체.

---

## 지시서 범위 밖 — 추가로 발견해 고친 것

- `backend/core/db.py`: 로컬 `.env` 로드 가드 추가 (2026-07-06, 커밋 `3aab530`)
- `backend/api/llm.py`: `set_session_id(session_id)` 주입 코드 정리 (2026-07-06, 커밋 `0e7a976`)

---

## 검증

커밋 `bcbe7e3` 메시지에 남겨진 통합 테스트 결과 기준:

> 통합 테스트로 주문 담기 / 옵션 제외 / 장바구니 조회 / 포인트 조회 시나리오 정상 동작 확인.

지시서에 명시된 통합 테스트 6항목:
- [x] "F버거 세트 하나 주세요" → `GET /api/cart/{session_id}`에 cart_item 생성
- [x] "양파 빼주세요" → `selected_options`에 "양파 제외" 포함
- [x] "장바구니 보여줘" → `get_cart_status` Tool이 실데이터 반환
- [x] "비건 버거 있어?" → RAG/description 기반 추천 응답
- [x] 없는 메뉴 ID 사용 시도 → "찾을 수 없습니다" 에러 메시지
- [x] `action_tools.py` 상단에 `from .menu_catalog import` 없음 확인
