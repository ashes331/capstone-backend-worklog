"""작업계획서 5번 섹션 하이퍼파라미터로 YOLOv8n 학습 (person/white_cane/wheelchair 3클래스).

COCO 사전학습 yolov8n.pt에서 시작 (기존 커스텀 체크포인트 없음 확인됨).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

if not hasattr(np, "trapz"):  # numpy>=2.0 에서 제거됨, ultralytics 8.3.40(tflite export 호환용)이 아직 사용
    np.trapz = np.trapezoid

from ultralytics import YOLO

DATA_YAML = Path(__file__).resolve().parents[1] / "data" / "merged_dataset" / "data.yaml"
RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DATA_YAML))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--batch", default=-1)
    parser.add_argument("--name", default="wheelchair_v1")
    args = parser.parse_args()

    model = YOLO("yolov8n.pt")
    model.train(
        data=args.data,
        imgsz=args.imgsz,
        batch=args.batch,
        epochs=args.epochs,
        patience=args.patience,
        amp=True,
        project=str(RUNS_DIR),
        name=args.name,
    )


if __name__ == "__main__":
    main()
