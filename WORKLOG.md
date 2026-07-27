# 작업 로그

날짜: 2026-07-26 ~ 2026-07-27
브랜치: `feature/backend-phase2` (원본: Capstone-F5/CapstoneProject)
최종 커밋: `8e96697`

## 1. 현황 파악

- 로컬 프로젝트와 GitHub `main` / `feature/backend-phase2` 브랜치 간 차이를 비교
- `feature/backend-phase2`가 origin엔 있지만 로컬엔 한 번도 체크아웃된 적 없다는 걸 확인, 로컬 브랜치로 새로 받음
- 담당 지시서(`지시서_관리자백엔드.md`) 확인: 1단계 마이그레이션 · Module A(인증) · Module B(메뉴관리) ·
  Module G(회원관리)가 내 담당 범위, Module C(주문로직) · D(환불) · E(주문관리) · F(쿠폰할인) · H(통계)는
  팀원(임지연) 담당

## 2. 지시서·명세서 대조 검증

`docs/백엔드_기능명세.md`(코드 스펙 원문)와 실제 커밋된 코드를 한 줄씩 대조하며 검증. 그 결과 서버가
아예 기동되지 않는 수준의 버그 9건을 발견.

### 발견한 버그

1. **파일명 오타** — `starts.py` / `starts_dao.py`가 실제로는 `stats.py`여야 함. `main.py`는
   처음부터 `stats` 모듈을 import하고 있어 `ModuleNotFoundError` 발생
2. **async/sync 세션 불일치** — Module C/D/E/F/H 6개 파일이 명세서 규정(async)과 다르게 sync
   `Session` + 존재하지 않는 `get_db()`를 참조해 import 시점에 오류
3. **관리자 인증 누락** — `admin/orders.py`, `coupons.py`, `discounts.py`, `payments.py`, `stats.py`
   5개 라우터에 `Depends(get_current_admin)`가 전혀 걸려있지 않아 로그인 없이 환불까지 호출 가능
4. **중복 함수로 깨진 Module G** — `user_dao.py`의 `adjust_points`가 두 번 정의되어, 뒤에 추가된
   sync 버전이 앞선 async 버전(회원 포인트 API)을 덮어씀
5. **스키마 클래스 중복 정의** — `order_schemas.py`의 `OrderAdminOut`이 두 번 정의되어 잘못된
   두 번째 정의가 올바른 첫 번째 정의를 덮어씀
6. **존재하지 않는 스키마 참조** — `order.py`가 `OrderCreateIn`·`cart_id`를 참조했지만 실제 스키마는
   `OrderIn`·`session_id` — 장바구니 조회 흐름 자체와 불일치
7. **필드명 불일치** — `OrderOut`/`OrderItemOut` 응답 조립 시 `order_id` 대신 `id`, 필수 필드
   `name_ko` 누락 등으로 Pydantic 검증 실패
8. **관계(relationship) 누락** — `UserCoupon` 모델에 `coupon` 관계가 없어 쿠폰 적용 로직에서
   `user_coupon.coupon` 접근 시 오류
9. **스키마 파일 들여쓰기 오류** — `payment_schemas.py`의 `class PaymentOut` 내부에 `import`
   문이 잘못 들여써져 있어 Pydantic 모델 정의 자체가 실패

## 3. 수정

위 9건 전부 수정. 세부 내용은 [`report.html`](./report.html)의 "핵심 수정 코드" 섹션 참고.

- 6개 파일 sync → async 전환 (`AsyncSession` / `get_session` / `select()` + `await db.execute()` 패턴으로 통일)
- 5개 admin 라우터에 `dependencies=[Depends(get_current_admin)]` 추가
- 파일명 정정: `starts.py` → `stats.py`, `starts_dao.py` → `stats_dao.py`
- `user_dao.py`의 중복 `adjust_points`를 async 버전 하나로 병합 (`reason` 파라미터 기본값 처리)
- `order_schemas.py`의 중복 `OrderAdminOut` 정리, `OrderOut`에 `status` 필드 추가
- `models.py`에 `UserCoupon.coupon` relationship 추가
- `order.py`를 실제 스키마(`OrderIn`/`session_id`)에 맞게 재작성, 장바구니 조회 흐름과 일치시킴
- `payment_schemas.py`의 잘못된 들여쓰기 import 수정

## 4. 로컬 실 DB 검증

- `.env`에 `ADMIN_JWT_SECRET` 등 관리자 인증 관련 값 채움
- `patch_db.py`로 로컬 `kiosk_db`에 `orders.status` / `user_coupon_id` 컬럼 반영
- `python-jose`, `passlib`, `bcrypt` 로컬 환경에 설치
- 서버를 직접 기동(`uvicorn main:app`)하고 curl로 Module A~H 전체 완료 기준을 하나씩 호출 검증

| 모듈 | 검증 내용 |
|---|---|
| 1단계 마이그레이션 | `orders.status` / `user_coupon_id` 컬럼 ALTER 완료 확인 |
| A (인증) | 로그인 성공 / 오답 401 / 토큰없음 401 / `/me` 200 확인 (STAFF→OWNER 403은 대상 엔드포인트 없어 스킵) |
| B (메뉴) | 가격 수정 즉시 반영, 진행중 주문 포함 메뉴 하드삭제 → 409 + 자동 품절 처리 확인 |
| C (주문 로직) | items 직렬화, 포인트 적립(124p), 쿠폰 10% 할인(620원) 정확 계산, 재사용 400 확인 |
| D (환불) | 포인트 원상복구(179→124), 쿠폰 복구 후 재사용 성공, 주문 CANCELLED 전환, 재환불 409 확인 |
| E (주문 관리) | 목록 조회, RECEIVED→COOKING 정상 전이, 역행 400 확인 |
| F (쿠폰) | 생성/발급/적용 전체 플로우 확인 |
| G (회원) | 전화번호 검색, 사유 없는 조정 400, 조정 후 고객 API 즉시 반영 확인 |
| H (통계) | RECEIVED→COMPLETED 진행 후 매출/인기메뉴 집계 정확 반영(4,320원, 1건) 확인 |

## 5. 형상관리

- `feature/backend-phase2`에 커밋 `8e96697`로 반영
- `origin/feature/backend-phase2`에 push 완료
- main 병합(PR)은 팀 판단으로 남겨둠 — 이 시점 기준 main엔 아직 Module A/B/G까지만 반영된 상태
