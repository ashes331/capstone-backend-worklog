# 작업 로그 — 제스처 인식 모듈 초기 버전 업로드

기간: 2026-05-19 (커밋 시각 00:28 KST — GitHub 커밋 목록에는 UTC 기준으로 5/18로 표시됩니다)
저장소: [Capstone-F5/CapstoneProject](https://github.com/Capstone-F5/CapstoneProject), `main` 이력에 포함
기준 문서: 확인된 지시서 없음
커밋: `5af1800` (GitHub 웹 "Add files via upload")

> 이 항목은 실시간으로 진행하며 기록한 게 아니라, 지난 git 커밋 히스토리와 코드를 근거로 사후에
> 재구성한 기록입니다. 이 작업을 하던 당시의 검증 기록이나 작업 배경은 남아 있지 않아서, 코드에서
> 확인되는 사실만 적었습니다.

이 시점의 작업은 **MediaPipe 손 랜드마크를 규칙으로 해석하는 제스처 인식 모듈 초기 버전과 그 웹캠
테스트 스크립트를 올린 것**입니다. 이후 다른 팀원이 여러 차례 고치며 크게 바뀌었기
때문에, 아래에서는 (1) 올린 내용, (2) 이후 이력, (3) 초기 버전의 한계 순서로 정리했습니다.

---

## 1. 올린 내용

| 파일 | 줄 수 | 역할 |
|---|---|---|
| `ai_modules/cv/gesture_module_API.py` | 107 | 카메라 프레임을 받아 제스처와 검지 끝 좌표를 반환하는 API (`detect_gesture(frame)`) |
| `ai_modules/cv/test_gesture.py` | 63 | 웹캠으로 위 모듈을 직접 확인하는 테스트 스크립트 |

### 인식 규칙 (`gesture_module_API.py`)

MediaPipe Hands(`max_num_hands=1`)로 손 랜드마크를 뽑고, 아래 순서로 판정합니다. 우선순위는 위에서부터입니다.

| 순서 | 제스처 | 판정 규칙 |
|---|---|---|
| 1 | `swipe_left/right/up/down` | 손목(0번) 좌표를 최근 15프레임 버퍼에 저장. 10프레임 이상 쌓이고, 버퍼 처음과 끝의 이동 거리가 **80픽셀 이상**이면 스와이프. 이동량이 큰 축으로 방향 결정 |
| 2 | `ok` | 엄지 끝(4번)과 검지 끝(8번)의 거리가 **0.05 미만**(정규화 좌표)이고, 중지·약지·소지가 펴져 있음(tip이 pip보다 위) |
| 3 | `finger_1` ~ `finger_5` | 엄지는 x축(4번 < 3번), 나머지 네 손가락은 tip이 pip보다 위에 있으면 펴진 것으로 세서 개수 반환 |

검지 끝 좌표는 제스처와 무관하게 항상 픽셀 값으로 함께 반환해서(`index_position`) 포인터로 쓸 수
있게 했습니다. 손이 없으면 스와이프 버퍼를 비우고, 예외가 나면 `error`에 메시지를 담아 반환합니다.

```python
def detect_gesture(frame):
    ...
    swipe = _detect_swipe()
    if swipe:
        return {"gesture": swipe, "index_position": index_position}
    if _is_ok(landmarks):
        return {"gesture": "ok", "index_position": index_position}
    finger_count = _count_fingers(landmarks)
    if finger_count > 0:
        return {"gesture": f"finger_{finger_count}", "count": finger_count, "index_position": index_position}
    return {"gesture": None, "index_position": index_position}
```

### 테스트 스크립트 (`test_gesture.py`)

웹캠을 열어 프레임마다 `detect_gesture`를 호출하고, 출력이 쏟아지지 않도록 10프레임마다만 확인합니다.
제스처가 바뀔 때만 이름을 출력하고(손가락 개수면 숫자도), 검지가 10픽셀 이상 움직였을 때만 좌표를
출력합니다. 화면에는 현재 제스처 이름을 그려주고 `q`로 종료합니다.

---

## 2. 이후 이력 (다른 작성자)

`git log`로 확인한 이 두 파일의 이후 변경입니다.

| 날짜 | 작성자 | 커밋 | 변경 |
|---|---|---|---|
| 2026-05-20 | 팀원 (GitHub: Yesung Cho) | `978aa65` | 엄지 판정을 손 방향(왼손/오른손)에 무관하게 바꿈 (`_is_thumb_open` 추가) |
| 2026-05-20 | 팀원 (GitHub: Yesung Cho) | `444a232` | `test_gesture.py` 정리 (커밋 제목이 "Potential fix for pull request finding"인 PR 지적 반영으로 보임) |
| 2026-05-25 | 팀원 (GitHub: yesung05) | `baa6019` | 두 파일을 크게 재작성 (두 파일 합쳐 536줄 추가·183줄 삭제). 커밋 제목: "핀치 동작 데이터 증강 필요, 80% 완료" |
| 2026-05-30 | 팀원 (GitHub: yesung05) | `6a7066b` | `gesture_module_API.py` 44줄 수정 (커밋 제목: "클라이언트 단 변경 전") |

현재는 `backend/core/gesture_service.py`가 같은 모듈(`gesture_module_API`)에서 `detect_gesture`,
`detect_gesture_from_landmarks`를 가져다 쓰고 있어서 파일 이름과 API 진입점은 그대로 남아 있습니다.
`gesture_classifier.py`에는 "모델 파일이 없으면 `gesture_module_API`가 규칙 기반으로 fallback"이라고
적혀 있어서, 지금은 학습된 분류기를 우선 쓰고 이 모듈의 규칙은 대체 수단으로 남은 구조로 보입니다.

---

## 3. 초기 버전의 한계

이후 커밋으로 **확인된 것**과 코드를 읽고 **추정한 것**을 구분해서 적었습니다.

- **[확인] 엄지 판정이 손 방향에 의존했습니다.** `landmarks[4].x < landmarks[3].x`는 한쪽 손
  방향만 가정한 규칙이라 왼손/오른손에 따라 결과가 달라집니다. 5/20에 다른 팀원이 상대 거리 방식
  (`_is_thumb_open`)으로 고쳤습니다.
- **[추정] 스와이프 기준이 해상도와 프레임 속도에 묶여 있었을 수 있습니다.** 80픽셀, 15프레임이라는
  고정값이라 카메라 해상도나 FPS가 바뀌면 같은 동작이 다르게 판정될 수 있습니다. 이후 재작성에서 이
  규칙이 어떻게 바뀌었는지, 실제로 문제가 됐는지는 확인하지 않았습니다.
- **[기록 없음] 이 시점의 검증 기록은 없습니다.** 테스트 스크립트로 웹캠에서 눈으로 확인하는
  방식이었을 것으로 보이며, 정확도를 수치로 잰 기록은 남아 있지 않습니다.
