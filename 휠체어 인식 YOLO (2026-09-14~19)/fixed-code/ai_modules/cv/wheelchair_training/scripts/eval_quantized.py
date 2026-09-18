"""양자화된 best_int8.tflite를 merged_dataset val로 검증 (양자화 전후 비교용)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

if not hasattr(np, "trapz"):  # numpy>=2.0 에서 제거됨, ultralytics 8.3.40이 아직 사용
    np.trapz = np.trapezoid

from ultralytics import YOLO
from ultralytics.nn import autobackend

TRAINING_ROOT = Path(__file__).resolve().parents[1]
QUANTIZED = TRAINING_ROOT / "runs" / "wheelchair_v2" / "weights" / "best_saved_model" / "best_int8.tflite"
DATA_YAML = TRAINING_ROOT / "data" / "merged_dataset" / "data.yaml"

# tflite_support 미설치로 export 시 메타데이터가 안 붙었음 -> AutoBackend 로드 직후 최소 메타데이터를 채워줌
_ORIG_INIT = autobackend.AutoBackend.__init__


def _patched_init(self, *args, **kwargs):
    _ORIG_INIT(self, *args, **kwargs)
    if getattr(self, "metadata", None) is None:
        self.metadata = {
            "batch": 1,
            "imgsz": [320, 320],
            "names": {0: "person", 1: "white_cane", 2: "wheelchair"},
            "stride": 32,
        }


autobackend.AutoBackend.__init__ = _patched_init


def main() -> None:
    model = YOLO(str(QUANTIZED))
    metrics = model.val(data=str(DATA_YAML), imgsz=320, split="val")
    print("\n=== 양자화 모델 검증 결과 ===")
    print("mAP50:", metrics.box.map50)
    print("mAP50-95:", metrics.box.map)
    print("per-class mAP50-95:", metrics.box.maps)


if __name__ == "__main__":
    main()
