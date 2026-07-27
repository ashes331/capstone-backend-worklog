# 작업 로그 — 지시서 기준 정리

기간: 2026-07-20 ~ 2026-07-26
브랜치: `feature/backend-phase2` (원본: [Capstone-F5/CapstoneProject](https://github.com/Capstone-F5/CapstoneProject))
기준 문서: `docs/지시서_관리자백엔드.md`, `docs/백엔드_기능명세.md`
최종 커밋: `8e96697`

지시서에 적힌 모듈 순서(1단계 → A → B → G / C → E → F → D → H)를 그대로 큰 틀로 삼고,
각 모듈에서 실제로 무슨 일이 있었는지 — 원래 구현 상태, 제가 발견한 문제, 수정한 코드,
검증 결과 순으로 정리했습니다.

---

## 김성원 담당 — 1단계 · Module A · Module B · Module G

### 1단계. 마이그레이션

**지시서 체크리스트**
- `models.py`의 `Order`에 `status`, `user_coupon_id` 컬럼 추가
- `AdminUser` 클래스 신규 추가
- `database/init.sql` 동기화
- `requirements.txt`에 `passlib[bcrypt]`, `python-jose[cryptography]` 추가
- `.env`에 `ADMIN_JWT_SECRET` 등 4개 값 추가

**진행 상황:** 팀원(진수민)이 이미 구현·커밋해둔 상태였습니다. 제가 확인한 건 로컬 반영 여부였는데,
로컬 `kiosk_db`는 이미 테이블이 있는 상태라 `create_all`이 컬럼을 추가해주지 않아 `patch_db.py`로
직접 `ALTER TABLE`을 실행해야 했습니다.

```python
# patch_db.py (임지연이 만들어둔 임시 마이그레이션 스크립트)
await conn.execute(text("ALTER TABLE orders ADD COLUMN status VARCHAR(32) DEFAULT 'RECEIVED';"))
await conn.execute(text("ALTER TABLE orders ADD COLUMN user_coupon_id VARCHAR(36);"))
```

`.env`엔 `ADMIN_JWT_SECRET`, `ADMIN_JWT_EXPIRE_MINUTES`, `ADMIN_BOOTSTRAP_USERNAME`,
`ADMIN_BOOTSTRAP_PASSWORD`를 이번에 직접 채웠습니다.

**검증:** `SHOW COLUMNS FROM orders`로 두 컬럼 반영 확인.

---

### Module A. 관리자 인증

**지시서 체크리스트**
- `security.py`(해시/토큰/인증), `admin_dao.py`, `admin_auth_schemas.py`, `api/admin/auth.py`
- 앱 시작 시 부트스트랩 OWNER 계정 자동 생성 (`admin_seed.py`)
- 완료 기준: 오답 비밀번호 401 / 토큰 없음 401 / STAFF의 OWNER 전용 호출 403 / `/me` 정상 응답

**진행 상황:** 전부 구현되어 있었고, 코드 자체엔 문제가 없었습니다.

**검증:**
```
POST /api/admin/auth/login {"username":"admin","password":"change-me-on-first-login"} → 200 (토큰 발급)
POST /api/admin/auth/login {"username":"admin","password":"wrongpassword"}            → 401
GET  /api/admin/users (토큰 없이)                                                       → 401
GET  /api/admin/auth/me (토큰 포함)                                                     → 200
```
STAFF→OWNER 403 항목은 `require_owner`를 실제로 사용하는 엔드포인트가 아직 없어 검증 대상 자체가 없었습니다
(버그 아님 — 추후 관리자 계정 관리 기능 추가 시 사용할 수 있도록 준비만 되어 있는 상태).

---

### Module B. 메뉴·카테고리 관리자 CRUD

**지시서 체크리스트**
- `api/admin/menu.py`, `menu_dao.py` 관리자용 함수
- 메뉴 CRUD 쓰기 작업 후 `ai_modules/llm/rag.py`의 `invalidate_cache()` 호출
- 완료 기준: 가격 수정 즉시 반영 / 품절 처리 후 음성주문 시 "품절" 안내 / 진행중 주문 포함 메뉴 하드삭제 시 409

**진행 상황:** 구현·연동 전부 정상이었습니다.

**검증:**
```
PATCH /api/admin/menu/items/{id} {"base_price": 6500}  →  GET /api/menu 즉시 6500 반영
DELETE /api/admin/menu/items/{id} (진행중 주문 포함)     →  409 + 자동 품절 처리(is_available=false)
```

---

### Module G. 회원·포인트 관리자 화면

**지시서 체크리스트**
- `api/admin/users.py`, `user_dao.py` 함수
- `PATCH /api/admin/users/{id}/points`는 Module C의 `adjust_points()` 재사용
- 포인트 조정 시 `reason` 필수
- 완료 기준: 전화번호 검색 정확 조회 / 조정 후 고객용 API에 즉시 반영

**진행 상황:** 원래 구현은 정상이었지만, **Module C(임지연) 작업이 나중에 같은 함수를 재정의하면서
같이 깨졌습니다.** `user_dao.py`에 `adjust_points`가 두 번 정의되어 있었고, 파이썬은 나중에 정의된
쪽으로 덮어쓰기 때문에 진수민이 만든 async 버전(아래)이 사라지고 임지연의 sync 버전이 그 자리를
차지하고 있었습니다.

```python
# 있었던 문제 — user_dao.py에 같은 이름 함수가 두 번 정의됨
async def adjust_points(db: AsyncSession, user_id, delta, reason: str) -> User | None:
    ...  # 진수민 · Module G, 회원 포인트 API가 이 시그니처를 기대함

def adjust_points(db: Session, user_id: str, delta: int) -> User:
    ...  # 임지연 · Module C, 뒤에 정의되어 위 함수를 덮어씀 (reason 인자도 없음)
```

```python
# 수정 — 하나로 병합, reason은 기본값 처리해서 두 호출부 모두 만족
async def adjust_points(
    db: AsyncSession, user_id: str, delta: int, reason: str = ""
) -> User | None:
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.current_points += delta
    await db.flush()
    logger.info("admin points adjustment: user_id=%s delta=%s reason=%s", user_id, delta, reason)
    return user
```

**검증:**
```
GET  /api/admin/users?phone=0101234                          → 회원 정확 조회
PATCH /api/admin/users/{id}/points {"delta":100,"reason":""} → 400 (사유 필수)
PATCH /api/admin/users/{id}/points {"delta":100,"reason":"test adjustment"} → 200, 즉시 반영
```

---

## 임지연 담당 — Module C · Module E · Module F · Module D · Module H

이 5개 모듈은 지시서·명세서 스펙(전부 `AsyncSession` 기반, admin 라우터는 예외 없이
`Depends(get_current_admin)`)과 다르게, **6개 파일이 sync `Session` + 존재하지 않는 `get_db()`를
참조**하고 있어 import 시점에 서버가 죽는 상태였습니다. 각 모듈에서 실제로 무엇이 문제였는지와
고친 코드를 정리합니다.

### Module C. 주문 처리 로직 보완

**지시서 체크리스트**
- `create_order`의 `items=[]` 하드코딩 제거, 실제 `OrderItemOut` 채우기
- 포인트 적립/차감 실제 반영, 쿠폰 적용 로직(`get_user_coupon_by_code`, `mark_coupon_used`, `restore_coupon`)
- `GET /api/orders/{id}`가 실제 `order.status` 반환
- 완료 기준: items 정확히 채워짐 / 포인트 적립·차감 반영 / 쿠폰 적용 및 재사용 시 400 / 실제 status 반환

**발견한 문제 3가지**
1. `order.py`가 존재하지 않는 `OrderCreateIn`·`cart_id`를 참조 — 실제 스키마는 `OrderIn`·`session_id`
   (다른 API들처럼 세션 기반 장바구니 조회 흐름과 안 맞았음)
2. `OrderOut`/`OrderItemOut` 조립 시 `order_id` 대신 `id`, 필수 필드 `name_ko` 누락으로 응답 검증 실패
3. `UserCoupon` 모델에 `coupon` 관계가 없어 `user_coupon.coupon` 접근 시 오류

```python
# 수정 전 — 존재하지 않는 스키마/필드 참조
async def create_order(body: OrderCreateIn, db: Session = Depends(get_db)):
    cart = db.query(Cart).filter(Cart.id == body.cart_id).first()
    ...
    return OrderOut(id=order.id, ..., items=[])  # name_ko 등 필수 필드 누락

# 수정 후 — 실제 스키마(session_id 기반)와 일치, items 정확히 채움
async def create_order(body: OrderIn, db: AsyncSession = Depends(get_session)):
    cart = await cart_dao.get_cart_with_items(db, body.session_id)
    ...
    return OrderOut(order_id=order.id, ..., items=[_to_order_item_out(i) for i in order_items])
```

**검증:**
```
POST /api/orders {session_id, phone:"01012345678"}
→ items 정확히 채워짐, points_earned=124, subtotal=12400

POST /api/orders {..., coupon_code:"WELCOME10"}   → discount_amount=620 (10% 정확 계산)
같은 쿠폰 재사용                                    → 400
```

---

### Module E. 주문 관리 (관리자)

**지시서 체크리스트**
- `order_dao.py`에 `list_orders`/`update_order_status` 추가
- 상태 전이 검증(`_is_valid_transition`) — 역방향 금지, `CANCELLED`는 `COMPLETED` 제외 항상 허용
- 완료 기준: 결제 완료 주문 즉시 `RECEIVED` 조회 / 앞으로만 전이 / `CANCELLED` 예외 허용

**발견한 문제:** `admin/orders.py`가 sync `Session` + `get_db()` 참조로 작성됨. `_is_valid_transition`
로직 자체는 지시서 그대로 정확히 구현되어 있었습니다.

```python
# 수정 전
def get_admin_orders(status=None, order_type=None, db: Session = Depends(get_db)):
    orders = order_dao.list_orders(db, status=status, order_type=order_type)

# 수정 후
async def get_admin_orders(status=None, order_type=None, db: AsyncSession = Depends(get_session)):
    orders = await order_dao.list_orders(db, status=status, order_type=order_type)
```

또한 라우터에 인증이 전혀 걸려있지 않아 `dependencies=[Depends(get_current_admin)]`을 추가했습니다.

**검증:**
```
GET   /api/admin/orders                                  → 목록 조회 정상
PATCH .../status?status=COOKING (RECEIVED에서)            → 200
PATCH .../status?status=RECEIVED (COOKING에서, 역행)       → 400
```

---

### Module F. 쿠폰·할인 관리자 CRUD

**지시서 체크리스트**
- `api/admin/coupons.py`, `discounts.py`, `dao/coupon_dao.py`, `dao/discount_dao.py`
- `DiscountIn` 검증 규칙(`target_type`에 따라 `menu_item_id`/`category_id` 필수)
- 완료 기준: 쿠폰 생성 후 코드로 정상 적용 / `max_usage_count` 도달 시 발급·사용 불가

**발견한 문제:** Module E와 동일하게 sync + `get_db()` 문제, 인증 누락.

```python
# 수정 전 — backend/dao/discount_dao.py
from sqlalchemy.orm import Session

def list_discounts(db: Session):
    return db.query(Discount).all()

# 수정 후
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def list_discounts(db: AsyncSession) -> list[Discount]:
    result = await db.execute(select(Discount))
    return result.scalars().all()
```

```python
# 수정 전 — backend/api/admin/discounts.py
router = APIRouter(prefix="/api/admin/discounts", tags=["admin-discounts"])

# 수정 후 — 인증 의존성 추가
router = APIRouter(
    prefix="/api/admin/discounts", tags=["admin-discounts"],
    dependencies=[Depends(get_current_admin)],
)
```

**검증:**
```
POST /api/admin/coupons {code:"WELCOME10", discount_type:"PERCENT", discount_value:10, ...} → 200
POST /api/admin/coupons/{id}/issue {phone:"01012345678"}                                    → 200
→ 실제 주문에서 코드로 적용, 정확히 10% 할인 확인
```

---

### Module D. 결제·환불 관리

**지시서 체크리스트**
- `api/admin/payments.py`, `payment_dao.py`에 `get_payment_by_order_id`/`list_payments`/`mark_refunded`
- 환불 시 포인트 원상복구 → 쿠폰 복구 → 결제 REFUNDED + 주문 CANCELLED
- `_is_valid_transition` 검증 없이 직접 상태 변경(완료 주문도 환불 가능해야 함)
- 완료 기준: 환불 시 결제·주문·포인트·쿠폰 동시 원상복구 / 이미 환불된 결제 재환불 시 409

**발견한 문제:** 역시 sync + `get_db()`, 인증 누락. 로직 자체(포인트/쿠폰 원상복구 순서, `_is_valid_transition`
우회)는 지시서 그대로 정확히 구현되어 있었습니다.

**검증:**
```
결제 생성 → 환불 실행
→ 포인트 179 → 124로 정확히 복구
→ 쿠폰 재사용 가능 상태로 복구 (실제로 새 주문에서 재적용 성공)
→ 주문 상태 CANCELLED 전환
재환불 시도 → 409
```

---

### Module H. 통계·대시보드

**지시서 체크리스트**
- `api/admin/stats.py`, `dao/stats_dao.py`
- 매출 요약 / 일자별 추이 / 인기 메뉴, `status='COMPLETED'` 건만 집계
- 완료 기준: 매출 합계가 실제 COMPLETED 주문 합과 일치 / 환불 건 제외

**발견한 문제:** 파일명 자체가 `starts.py`/`starts_dao.py`(오타)였습니다. `main.py`는 처음부터
`stats` 모듈을 import하고 있었기 때문에, 이 오타 하나 때문에 **서버 전체가 기동 자체를 못 하는**
가장 치명적인 문제였습니다.

```python
# backend/main.py — 원래부터 이렇게 import 하고 있었음 (여긴 수정 안 함)
from backend.api.admin import stats as admin_stats
```
```
❌ 실제 파일:  backend/api/admin/starts.py, backend/dao/starts_dao.py
✅ 수정 후:    backend/api/admin/stats.py, backend/dao/stats_dao.py  (파일명 정정 + async 전환 + 인증 추가)
```

**검증:**
```
주문을 RECEIVED → COOKING → READY → COMPLETED까지 진행
GET /api/admin/stats/summary        → {"today_sales": 4320.0, "order_count": 1, ...}
GET /api/admin/stats/popular-items  → 판매 수량/매출 정확 집계
```

---

## 최종 검증 및 형상관리

- `.env`에 관리자 인증 값 채움, `patch_db.py`로 로컬 DB 컬럼 반영, `python-jose`/`passlib`/`bcrypt` 설치
- 서버 직접 기동 후 위 9개 섹션의 완료 기준을 전부 curl로 실제 호출해 확인
- `feature/backend-phase2`에 커밋(`8e96697`) 후 origin에 push
- main 병합(PR)은 이 시점 기준 아직 진행 전 — main엔 Module A/B/G까지만 반영된 상태
