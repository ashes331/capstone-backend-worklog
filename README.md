# Capstone 작업 로그

**보고서 목록 바로 보기: [ashes331.github.io/capstone-backend-worklog](https://ashes331.github.io/capstone-backend-worklog/)**

캡스톤 프로젝트([Capstone-F5/CapstoneProject](https://github.com/Capstone-F5/CapstoneProject)) 작업 중
제가 직접 진행한 부분을 지시서 단위로 정리하는 저장소입니다. 작업은 `{지시서 작업명} ({작업 기간})`
폴더 하나에 작업 로그·수정 코드·보고서를 함께 담는 방식으로 쌓아갑니다.

> 팀 저장소 자체는 이미 Public — 이 저장소는 그중 **제가 직접 발견·수정·검증한 부분만** 정리한 개인 기록입니다.

## 작업 목록

| 기간 | 작업 | 보고서 |
|---|---|---|
| 2026-07-06~12 | AI Tool 파트 (action_tools.py 재작성) | [report.html (렌더링됨)](https://ashes331.github.io/capstone-backend-worklog/AI%20Tool%20%ED%8C%8C%ED%8A%B8%20%282026-07-06~12%29/report.html) |
| 2026-07-20~26 | 관리자 백엔드 버그 수정 및 검증 | [report.html (렌더링됨)](https://ashes331.github.io/capstone-backend-worklog/%EA%B4%80%EB%A6%AC%EC%9E%90%20%EB%B0%B1%EC%97%94%EB%93%9C%20%282026-07-20~26%29/report.html) |
| 2026-09-14~19 | 휠체어 인식 YOLO 재학습 및 감지 연동 | [report.html (렌더링됨)](https://ashes331.github.io/capstone-backend-worklog/%ED%9C%A0%EC%B2%B4%EC%96%B4%20%EC%9D%B8%EC%8B%9D%20YOLO%20%282026-09-14~19%29/report.html) |

---

## 2026-07-06~12 — AI Tool 파트

**보고서: [ashes331.github.io/capstone-backend-worklog](https://ashes331.github.io/capstone-backend-worklog/) 목록에서 확인**

`feature/llm-db-tools` 작업. 지시서 역할 분배는 **김성원 — `action_tools.py` 재작성** /
**임지연 — `api_client.py`, `rag.py`, `prompts.py`, `action_context.py`**였습니다.

> 이 항목은 실시간으로 진행하며 기록한 게 아니라, 지나간 git 커밋 히스토리를 근거로
> 사후에 재구성한 기록입니다.

### 폴더 구성

| 경로 | 내용 |
|---|---|
| [`AI Tool 파트 (2026-07-06~12)/report.html`](<./AI Tool 파트 (2026-07-06~12)/report.html>) | 담당별 지시서 대조 체크리스트, 핵심 수정 코드, 발견한 문제를 정리한 웹 문서 |
| [`AI Tool 파트 (2026-07-06~12)/WORKLOG.md`](<./AI Tool 파트 (2026-07-06~12)/WORKLOG.md>) | 담당자별 지시서 체크리스트, 진행 상황, 발견해 고친 문제와 코드, 검증 결과 |
| [`AI Tool 파트 (2026-07-06~12)/fixed-code/`](<./AI Tool 파트 (2026-07-06~12)/fixed-code>) | 관련 커밋 시점의 `ai_modules/llm/`, `backend/api/llm.py`, `backend/core/db.py` |

### 요약

- 본인 담당(`action_tools.py`)은 지시서대로 재작성 완료, 이후 `menu_item_id`(UUID) 조회 수단이
  없다는 걸 발견해 `list_menu` Tool을 추가로 만들고, 가격 캐스팅 크래시 버그도 수정
- 팀원(임지연) 담당 파일(`rag.py`, `prompts.py`, `api_client.py`)에서도 API 키 미설정 시
  인덱스 빌드가 죽는 문제, 시나리오 누락, 백엔드 스키마와 필드명이 안 맞는 문제를 발견해 보완
  — 관리자 백엔드 작업 때와 같은 패턴

---

## 2026-07-20~26 — 관리자 백엔드

**보고서: [ashes331.github.io/capstone-backend-worklog](https://ashes331.github.io/capstone-backend-worklog/) 목록에서 확인**

`feature/backend-phase2` 작업 중, 서버 기동 자체를 막고 있던 버그들을 찾아 고치고 실 DB로
전체 기능을 검증했습니다.

### 담당 범위

지시서(`지시서_관리자백엔드.md`) 기준 담당은 1단계 마이그레이션 · Module A(인증) · Module B(메뉴관리) ·
Module G(회원관리)였고, 이 부분은 팀원이 먼저 구현해둔 상태였습니다. 이후 팀원(임지연)이 담당한
Module C(주문로직) · D(환불) · E(주문관리) · F(쿠폰할인) · H(통계)까지 합쳐진 브랜치를 검증하는 과정에서,
서버가 아예 기동되지 않는 수준의 버그 9건을 발견해 전부 수정했습니다.

### 폴더 구성

| 경로 | 내용 |
|---|---|
| [`관리자 백엔드 (2026-07-20~26)/WORKLOG.md`](<./관리자 백엔드 (2026-07-20~26)/WORKLOG.md>) | 지시서 모듈 순서를 기준으로 발견한 문제·수정 코드·검증 결과를 정리한 작업 기록 |
| [`관리자 백엔드 (2026-07-20~26)/fixed-code/`](<./관리자 백엔드 (2026-07-20~26)/fixed-code>) | 이번에 수정한 backend 코드 16개 파일 |
| [`관리자 백엔드 (2026-07-20~26)/report.html`](<./관리자 백엔드 (2026-07-20~26)/report.html>) | 모듈별 테스트 결과, 지시서 대조 체크리스트, 핵심 수정 코드를 정리한 웹 문서 |

### 요약

- **발견·수정한 버그**: 9건 (async/sync 세션 불일치, 관리자 인증 누락, 파일명 오타, 중복 함수 정의로 인한 연쇄 파손 등)
- **검증**: 로컬 MySQL에 연결해 Module A~H 전체를 실제 API 호출로 완료 기준 확인
- **결과**: `feature/backend-phase2`에 커밋 후 push 완료

---

## 2026-09-14~19 — 휠체어 인식 YOLO

**보고서: [ashes331.github.io/capstone-backend-worklog](https://ashes331.github.io/capstone-backend-worklog/) 목록에서 확인**

`feat/issue-66-wheelchair-detection` 작업(이슈 #66, PR #73). 기존 YOLOv8n(person + white_cane)에 휠체어를
추가해 재학습·양자화하고, 휠체어 감지 시 제스처 인식 모드가 자동으로 켜지도록 백엔드·프론트를 연동했습니다.

### 폴더 구성

| 경로 | 내용 |
|---|---|
| [`휠체어 인식 YOLO (2026-09-14~19)/WORKLOG.md`](<./휠체어 인식 YOLO (2026-09-14~19)/WORKLOG.md>) | 이슈 #66 체크리스트 기준으로 진행 상황·발견한 문제·수정 코드·검증 결과를 정리한 작업 기록 |
| [`휠체어 인식 YOLO (2026-09-14~19)/fixed-code/`](<./휠체어 인식 YOLO (2026-09-14~19)/fixed-code>) | 이번에 수정·추가한 소스 18개 (감지기·서비스·WebSocket, 프론트 훅·`App.jsx`, 학습 파이프라인 스크립트) |
| [`휠체어 인식 YOLO (2026-09-14~19)/report.html`](<./휠체어 인식 YOLO (2026-09-14~19)/report.html>) | 체크리스트 대조, 검증 결과, 핵심 수정 코드, 발견한 문제를 정리한 웹 문서 |

### 요약

- **모델**: person / white_cane / wheelchair 3클래스 YOLOv8n을 재학습해 INT8로 양자화. 같은 val 셋 기준 mAP50은
  person 0.794 → 0.846, white_cane 0.969 → 0.983, wheelchair 0.964(신규)
- **발견·수정한 문제**: 9건. 가장 큰 것은 사람이 탄 휠체어가 wheelchair로 학습되지 않던 데이터 문제로, 검증 mAP로는
  드러나지 않고 실사진 테스트에서 발견해 재학습
- **연동**: 휠체어 감지 → 제스처 모드 자동 ON + 안내 음성, `useApproachDetector` 훅을 `App.jsx`에 처음 연결
- **미확인**: 카메라를 켠 실기기 동작 (서버 WebSocket 시나리오와 프론트 빌드까지만 확인)
- **결과**: 커밋 4건 push, PR #73 생성 (머지 전)
