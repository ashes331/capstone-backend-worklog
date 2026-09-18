# 휠체어 인식 모델 학습 파이프라인 (Issue #66)

person / white_cane / wheelchair 3클래스 YOLOv8n(320x320) 재학습 및 INT8 양자화 스크립트 모음.
결과물은 `ai_modules/cv/models/best.pt`, `best_int8.tflite`.

## 준비물 (저장소에 없음)

| 항목 | 위치/방법 |
|---|---|
| 원본 데이터셋 | `visionguide_dataset`, `wheelchair.v5i.yolov8` (Roboflow: kyushu-university-to5hs/wheelchair-9qvfx v5). 스크립트 기본 경로가 `C:\Users\SAMSUNG\Downloads\...`로 하드코딩돼 있으니 다른 PC에서는 `merge_datasets.py`, `debug_class_order.py`의 경로와 `pseudo_label_wheelchair.py --src`를 바꿀 것 |
| 구모델 (pseudo-labeling용) | `git show 8511944^:ai_modules/cv/models/best_int8.tflite > base_model/original_person_cane_int8.tflite` (`base_model/`은 gitignore) |
| 가상환경 | Python 3.12, `torch==2.6.0+cu124`, `tensorflow`, `onnx2tf==1.22.3` 등 |

## 실행 순서 (`scripts/`에서)

1. `pseudo_label_wheelchair.py` — 구모델로 `people_wheelchair` 박스를 person 박스로 정제, 원본 박스는 wheelchair로도 추가
2. `visualize_review.py` — 결과 육안 검수용 이미지 생성
3. `merge_datasets.py` — 두 데이터셋을 `person=0, white_cane=1, wheelchair=2`로 병합
4. `oversample_wheelchair.py` — wheelchair 포함 이미지 3배 오버샘플링
5. `train.py --name <run이름>` — COCO `yolov8n.pt`에서 80 epoch
6. `quantize.py` — INT8 TFLite 변환
7. `eval_quantized.py`, `eval_old_model.py` — 양자화 후/구모델 대비 검증

## 알아둘 점

- **`ultralytics==8.3.40` 고정**: 최신 버전은 tflite export를 Windows에서 막아둠. 대신 이 버전은 numpy 2.x와 충돌(`np.trapz`)해서 `train.py`, `eval_quantized.py`에 shim이 들어 있음.
- `tflite_support`가 Windows에서 설치 실패(C++ 컴파일러 필요)해서 export의 메타데이터 삽입 단계가 에러로 끝나지만, `.tflite` 파일은 그 전에 정상 생성됨. 메타데이터가 없어 `eval_quantized.py`는 AutoBackend를 패치해서 검증함. 서비스 추론(`approach_detector.py`)은 메타데이터를 쓰지 않음.
- 구모델의 클래스 순서는 `0=white_cane, 1=person`이었음 (`KNOWN_ISSUE_class_order_bug.md` 참고).
