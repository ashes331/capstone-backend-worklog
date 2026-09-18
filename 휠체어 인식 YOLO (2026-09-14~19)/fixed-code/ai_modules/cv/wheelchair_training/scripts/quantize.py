"""학습된 best.pt를 INT8 TFLite로 양자화 (계획서 6번 리스크: calibration 이미지 200~300장 이상 확보).

ultralytics export(format='tflite', int8=True, data=...)는 data.yaml의 train 이미지 일부를
calibration 대표 이미지로 사용한다.
"""
from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

TRAINING_ROOT = Path(__file__).resolve().parents[1]
BEST_PT = TRAINING_ROOT / "runs" / "wheelchair_v2" / "weights" / "best.pt"
DATA_YAML = TRAINING_ROOT / "data" / "merged_dataset" / "data.yaml"


def main() -> None:
    model = YOLO(str(BEST_PT))
    exported = model.export(format="tflite", int8=True, data=str(DATA_YAML), imgsz=320)
    print(f"\nquantized model: {exported}")


if __name__ == "__main__":
    main()
