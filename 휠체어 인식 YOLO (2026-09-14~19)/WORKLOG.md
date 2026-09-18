# 작업 로그 — 이슈 #66 기준 정리

기간: 2026-09-14 ~ 2026-09-19
브랜치: `feat/issue-66-wheelchair-detection` (원본: [Capstone-F5/CapstoneProject](https://github.com/Capstone-F5/CapstoneProject))
PR: #73 (머지 전)
기준 문서: Issue #66, `docs/AI 질의.md`(팀 기획 대화록), 개인 작업 계획서
커밋: `8511944`, `03e39a5`, `561ad85`, `0b49f65`

이슈 #66은 "기존 YOLO 모델에 휠체어를 추가하고, 감지 시 동작까지 연결"하는 작업입니다. 이슈의
체크리스트 5개(데이터셋 → 재학습 → 양자화 → 백엔드 → 프론트)를 순서대로 큰 틀로 삼고, 각 단계에서
실제로 무슨 일이 있었는지 — 진행 상황, 발견한 문제, 수정한 코드, 검증 결과 순으로 정리했습니다.

---

## 이슈 #66 체크리스트 대조

| # | 이슈 항목 | 결과 |
|---|---|---|
| 1 | 휠체어 데이터셋 수집 및 라벨링 | 데이터셋은 제공받았고, 라벨 문제를 pseudo-labeling으로 보완 |
| 2 | YOLOv8 재학습 | person / white_cane / wheelchair **3클래스**로 완료 (작업 계획서 기준) |
| 3 | INT8 양자화 → `best_int8.tflite` 갱신 | 완료, 배포 경로의 파일을 교체 |
| 4 | 백엔드 감지 로직에 휠체어 처리 추가 | 완료 |
| 5 | 프론트 WebSocket 훅에서 휠체어 이벤트 처리 | 완료 |

**설계 기준.** 이슈 본문을 요약해서 읽었을 때는 "휠체어 감지 시 음성인식 모드 활성화"로 보였는데,
팀 기획 대화록(`docs/AI 질의.md`, 9/13 커밋)에는 대상별 전환 모드가 **시각장애인(흰 지팡이) → 음성,
휠체어 → 제스처**로 여러 번 일관되게 적혀 있었습니다. 기획 문서를 따라 휠체어는 **제스처 모드**만 켜기로
했습니다. 안내 음성(TTS)은 흰 지팡이와 같은 방식(10초 간격 3회)으로 두 대상 모두 나갑니다.

---

## 1. 데이터셋 분석

**진행 상황:** 계획서는 "신규 데이터셋에 휠체어 탄 사람의 `person` 라벨이 없다"고 가정하고 있었는데,
실제로 라벨 파일을 세어보니 달랐습니다.

`wheelchair.v5i.yolov8` (`people_wheelchair` / `person` / `wheelchair`, train 기준):

| 클래스 | 개수 |
|---|---|
| `people_wheelchair` | 642 |
| `person` | 2,271 |
| `wheelchair` | 395 |

`person`은 이미 많았고, 문제는 **휠체어를 탄 사람만 `people_wheelchair`라는 별도 클래스**로, 그것도 사람과
휠체어를 통째로 감싸는 느슨한 박스로 라벨링되어 있다는 점이었습니다. 이걸 그냥 버리면 "휠체어 탄 사람
영역 = 배경"으로 학습되어 `person` 성능이 떨어집니다.

**발견한 문제:** `visionguide_dataset`은 루트의 `images/`·`labels/`(9,308장, white_cane만 있음)와 실제
학습용 `train/`·`val/`·`test/`(train 11,116장, white_cane 7,572개 / person 23,606개)가 따로 있었습니다.
처음에 루트 폴더로 검증하다가 "person 라벨이 0개"라는 잘못된 결과를 얻어서 한참 헤맸고, `data.yaml`이
가리키는 서브폴더로 바꿔서 해결했습니다.

---

## 2. Pseudo-labeling — 기존 모델로 person 박스 정제

기존 `best_int8.tflite`(person + white_cane)로 `people_wheelchair` 874개 인스턴스에 추론을 돌려, 타이트한
person 박스로 교체하고 실패하면 원본 느슨한 박스를 폴백으로 씁니다. (`pseudo_label_wheelchair.py`)

**발견한 문제 1 — 클래스 순서가 코드와 반대였습니다 (프로덕션 버그).**
처음 돌렸을 때 874건 전부 실패(0건 성공)해서 원인을 파봤습니다. `visionguide_dataset` 정답 박스 위치에서
모델이 어느 클래스로 반응하는지 통계로 대조했습니다.

```
white_cane 정답 위치 (190개) → 모델 class0 평균 0.350 / class1 0.000
person     정답 위치 (626개) → 모델 class0 0.000     / class1 평균 0.420
```

즉 구모델은 **class0 = white_cane, class1 = person**인데, 배포 코드 `approach_detector.py`는
`WHITE_CANE_CLASS_ID = 1`로 반대로 잡고 있었습니다. 그대로였다면 "사람이 감지되면 흰 지팡이로 판정"하는
식으로 오작동했을 것입니다. (`debug_class_order.py`로 재현 가능. 이번 PR에서 모델을 교체하며 함께 해소)

**발견한 문제 2 — 제 스크립트의 좌표 스케일 오류.** 모델 출력 박스 좌표가 이미 0~1로 정규화되어 있는데,
입력 해상도(320)의 픽셀 값이라고 가정하고 다시 스케일링해서 IoU 매칭이 전부 실패했습니다.

```python
# 수정 전 — 입력 해상도 기준 픽셀로 착각
x1 = (cx - w / 2) * sx      # sx = img_w / 320

# 수정 후 — 정규화 좌표를 원본 이미지 크기에 곱함
x1 = (cx - w / 2) * img_w
```

**검증:** 수정 후 874건 중 **642건(73%)이 타이트한 person 박스로 교체**, 232건은 폴백. 두 경우 모두
박스를 그려 육안 검수했고 학습에 쓸 수 있는 품질이었습니다.

---

## 3. 데이터 병합 · 재학습 · 양자화 (v1)

`visionguide`(white_cane 0→1, person 1→0으로 리매핑)와 pseudo-labeled wheelchair 데이터를
`person=0, white_cane=1, wheelchair=2` 스킴으로 병합했습니다. (`merge_datasets.py`)
wheelchair가 person의 1/67이라 wheelchair 포함 이미지를 3배 오버샘플링했습니다. (`oversample_wheelchair.py`)

COCO 사전학습 `yolov8n.pt`에서 80 epoch(imgsz 320) 학습 → 1.5시간. 기존 커스텀 체크포인트(`.pt`)는
남아있지 않고 양자화된 tflite만 있어서, 재학습 시작점으로 쓸 수 없었기 때문에 처음부터 학습했습니다.

**발견한 문제 3 — Windows에서 tflite 변환이 막혀 있었습니다.** 세 가지가 연달아 나왔습니다.
- 최신 `ultralytics`(8.4.x)는 tflite export를 "LiteRT" 방식으로 바꾸면서 Linux/macOS만 허용 → `8.3.40`으로 고정
- `tflite_support`가 C++ 컴파일러를 요구해 설치 실패 → 메타데이터 삽입 단계만 에러, INT8 변환 자체는 정상 완료
  (서비스 추론은 메타데이터를 쓰지 않아 영향 없음)
- 구버전 `ultralytics`가 numpy 2.x에서 제거된 `np.trapz`를 써서 학습 중 검증 단계에서 죽음 → `np.trapz = np.trapezoid` shim 추가

---

## 4. 백엔드 · 프론트 연동

`approach_detector.py`를 3클래스 출력에 맞게 다시 쓰고, `approach_service.py`에 트리거별(흰 지팡이 / 휠체어)
안내 문구와 프론트가 켤 모드(`voice` / `gesture`)를 추가했습니다.

```python
ANNOUNCEMENT_MESSAGES = {
    "white_cane": "햄버거 주문을 위한 키오스크 입니다.",
    "wheelchair": "휠체어 이용 고객님, 손동작으로 메뉴를 선택하실 수 있습니다.",
}
MODE_ACTIONS = {"white_cane": "voice", "wheelchair": "gesture"}
```

**발견한 문제 4 — `useApproachDetector` 훅이 어디에서도 연결되어 있지 않았습니다.** 기획 문서에는 시각장애인
쪽이 "완료"로 적혀 있었지만, 코드를 보면 훅이 정의만 되어 있고 어떤 화면에도 쓰이지 않았습니다. 이번에
`App.jsx`에 처음 연결했고, 휠체어 감지 시 `setGestureEnabled(true)`를 호출합니다. 흰 지팡이 감지 시
음성 대화 모드(ChatPanel) 자동 전환은 이슈 #66 범위가 아니라 구현하지 않았습니다.

---

## 5. 실사용 테스트에서 찾은 치명적 문제 (v2 재학습)

**진행 상황:** v1을 프로덕션에 연결해 사람이 실제로 탄 휠체어 사진으로 돌려봤더니 **거의 감지되지
않았습니다** (신뢰도 0.0001 ~ 0.02). 검증 mAP(wheelchair 0.968)는 높게 나왔는데도 그랬습니다.

**원인:** 원본 데이터셋에서 `people_wheelchair`(사람이 탄 휠체어)와 `wheelchair`(빈 휠체어·제품 사진)가
거의 겹치지 않았습니다. (Python으로 재확인: `people_wheelchair`만 있는 이미지 496장, `wheelchair`만 있는 이미지
379장, 둘 다 있는 이미지 2장) 제 pseudo-labeling은 `people_wheelchair`를 person으로만 바꾸고 wheelchair
박스를 남기지 않아서, 모델이 wheelchair를 **빈 휠체어 사진으로만** 배웠습니다. 실제 키오스크에서 마주칠
"휠체어 탄 사람이 다가오는" 장면은 wheelchair 학습에 전혀 없었고, val 셋도 같은 좁은 분포라 mAP만으로는
드러나지 않았습니다.

```python
# pseudo_label_wheelchair.py — people_wheelchair 인스턴스마다 wheelchair 박스도 함께 남김
wheelchair_px = wheelchair_px + pw_px
```

수정 후 train의 wheelchair 라벨이 395개 → 1,037개(오버샘플링 후 3,111개)로 늘었습니다.

**발견한 문제 5 — 재학습 중 제가 만든 순환 참조.** 프로덕션 모델 경로를 신모델로 교체해둔 상태에서 다시
pseudo-labeling을 돌리니, 구모델이 아니라 방금 교체한 신모델(클래스 순서가 다름)을 읽어서 또 0건 성공이
나왔습니다. git 히스토리에서 구모델을 복원해 `base_model/`에 두고 스크립트가 그걸 보게 했습니다.

**발견한 문제 6 — 훅이 매 렌더마다 카메라와 WebSocket을 재연결했습니다 (제 연동 버그).** 훅의 `useEffect`가
콜백을 의존성으로 쓰는데, `App.jsx`에서 매 렌더 새 화살표 함수를 넘겼고 `App`은 제스처 HUD 때문에 자주
리렌더됩니다.

```jsx
// 수정 전
useApproachDetector({
  enabled: true,
  onModeAction: (action) => { if (action === 'gesture') setGestureEnabled(true) },
})

// 수정 후 — 안정적인 참조
const handleApproachModeAction = useCallback((action) => {
  if (action === 'gesture') setGestureEnabled(true)
}, [])
useApproachDetector({ enabled: true, onModeAction: handleApproachModeAction })
```

**발견한 문제 7 — 안내가 끝없이 반복되고 터치해도 멈추지 않았습니다.** 마지막에 전체를 다시 점검하면서
서버 로직을 실제로 돌려 재현했습니다. 안내 3회가 끝나 `mode_ended`가 나가도 대상이 계속 화면에 있으면 다음
프레임에서 바로 다시 시작됐고(7초 테스트에서 안내 18회·종료 6회), 터치(`user_input`)로 종료 ack를 받아도 다음
프레임에서 재시작됐습니다. 게다가 훅이 제공하는 `notifyUserInput`을 `App.jsx`가 호출하지도 않았습니다.
프로젝트 문서(현황보고)의 시나리오는 "10초마다 최대 3회 안내, 터치 시 IDLE 복귀"까지만 정해져 있어서, 종료 후
재감지 조건은 "대상이 화면에서 사라질 때까지 기다리기"로 정해 보충했습니다.

```python
# approach_service.py — 종료(3회 완료/터치) 시 잠금, 대상이 연속 6프레임(약 3초) 사라져야 해제
def finish(self) -> None:
    self.reset()
    self.latched = True
    self.absent_frames = 0

if session.latched:
    if trigger is None:
        session.absent_frames += 1
        if session.absent_frames >= REARM_ABSENT_FRAMES:
            session.latched = False
            session.absent_frames = 0
    else:
        session.absent_frames = 0
elif not session.mode_on and trigger:
    session.activate(trigger)
```

안내 중일 때만 터치가 잠금을 걸고(평소 화면을 만지는 것으로 다음 대상 감지를 막지 않도록), 프론트는 화면
터치·클릭 시 `notifyUserInput`을 호출하도록 연결했습니다. 안내 3회 후 재시작 없음, 3프레임 깜빡임엔 잠금 유지,
6프레임 부재 후 재감지, 터치 후 재시작 없음, 평소 터치는 감지를 막지 않음까지 11개 항목을 다시 테스트해 통과했고
기존 15개 시나리오도 그대로 통과했습니다.

**검증 (v2, 같은 val 셋):**

| 클래스 | 기존 모델 mAP50 | v2 (INT8) mAP50 | v2 양자화 전 |
|---|---|---|---|
| person | 0.794 | 0.846 | 0.852 |
| white_cane | 0.969 | 0.983 | 0.984 |
| wheelchair | - | 0.964 | 0.973 |

- 기존 두 클래스는 회귀 없이 개선, 양자화 전후 차이는 미미
- 이전에 실패하던 사람이 탄 휠체어 사진: 신뢰도 **0.89 ~ 0.92**로 정상 감지, 흰 지팡이 사진은 0.74로 그대로 정상
- wheelchair mAP50-95는 v1(0.906)보다 낮아진 0.835. 이제 학습·검증에 느슨한 통합 박스가 포함되어 박스 정밀도는
  손해를 보지만, 실제로 감지가 되는지(mAP50)는 유지되어 의도한 트레이드오프

---

## 최종 검증 및 형상관리

- 실제 `/ws/approach` WebSocket에 사진 프레임을 보내 시나리오를 확인했습니다 (TTS는 가짜로 대체, 사진은 학습 셋 이미지라
  스모크 테스트 수준). 휠체어 → `gesture`, 흰 지팡이 → `voice`, 안내 3회 후 종료, 대상 없음 → 모드 꺼짐, 터치 시 즉시 종료 모두 통과
- 프론트는 `npm ci` + 빌드까지 확인
- **미확인:** 카메라를 켠 실기기 동작 (감지용 카메라와 제스처용 카메라 동시 사용, 오디오 재생, 훅 재연결 수정 효과)
- 검증 셋(1,757장)으로 실제 감지율도 측정 (모델이 학습에 안 쓴 이미지지만 best epoch 선택에는 쓴 셋이라 다소 낙관적):
  wheelchair 감지 96.3~96.6%, 휠체어 없는 이미지 오탐 0.5%, white_cane 감지 90.7~96.5%, 오탐 0%
  (원본 크기 / 웹캠 형태 320x240 JPEG 60 기준)
- **알려진 한계:** 프레임 1장의 감지만으로 발동(여러 프레임 확인 로직 없음), 종료 후 재감지 조건은 임시(대상이 약 3초 사라질 때까지)
- `feat/issue-66-wheelchair-detection`에 커밋 4건(`8511944`, `03e39a5`, `561ad85`, `0b49f65`) 후 push, PR #73 생성 (머지 전)
- 동작 변경 참고: 훅을 처음 연결하면서 앱 시작 시 감지용 카메라·WebSocket이 항상 켜지고, 흰 지팡이 감지 시 기존 안내 음성이
  처음으로 실제 재생됨
