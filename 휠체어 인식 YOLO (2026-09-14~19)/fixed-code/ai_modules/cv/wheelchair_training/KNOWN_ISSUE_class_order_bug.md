# 발견된 버그 (Issue #66 PR에서 해소됨)

재학습 전 `ai_modules/cv/approach_detector.py`의 `WHITE_CANE_CLASS_ID = 1`이 당시 모델(`best_int8.tflite`, 2클래스)의 실제 클래스 순서와 반대였습니다.

## 근거

`visionguide_dataset/datasets/train`의 정답 라벨(`white_cane=0, person=1`, data.yaml 기준)과
`best_int8.tflite`의 실제 출력을 626개(person) / 190개(white_cane) 정답 박스 위치에서 통계적으로 대조한 결과:

- white_cane 정답 위치 → 모델 **class0** 평균 confidence 0.350, class1은 0.000
- person 정답 위치 → 모델 **class1** 평균 confidence 0.420, class0은 0.000

즉 구모델은 **class0 = white_cane, class1 = person**이었고, 당시 `WHITE_CANE_CLASS_ID = 1`은 반대로 설정되어 있었습니다.
그대로였다면 흰 지팡이 접근 감지가 "사람이 감지되면 흰 지팡이로 판정"하는 식으로 오작동했을 것입니다.

재현/검증 스크립트: `ai_modules/cv/wheelchair_training/scripts/debug_class_order.py`

## 상태

- 2026-09-14 확인. **해소됨**: 이 PR에서 모델을 `person=0, white_cane=1, wheelchair=2` 순서의 3클래스 모델로 교체하고, `approach_detector.py`의 클래스 ID도 그에 맞게 재작성함.
- 아래 근거는 교체 전 구모델 기준이며 기록용으로 남겨둠. 구모델은 git 히스토리(`ai_modules/cv/models/best_int8.tflite`, 이 PR 이전 커밋)에서 복원할 수 있음.
