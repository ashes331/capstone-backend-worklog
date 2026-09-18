"""기존 best_int8.tflite(2클래스: white_cane=0, person=1)를 merged val 셋으로 검증해
새 3클래스 모델과 person/white_cane 성능을 직접 비교한다.

merged_dataset/val 라벨(person=0, white_cane=1, wheelchair=2)을 기존 모델 스킴으로
리매핑한 evalsets/val_old_scheme 를 만들고(이미지는 하드링크로 복제 없이 재사용),
ultralytics로 best_int8.tflite를 그 위에서 검증한다.
"""
from __future__ import annotations

import os
from pathlib import Path

from common import TARGET_PERSON, TARGET_WHITE_CANE, read_yolo_labels, write_yolo_labels
from ultralytics import YOLO

TRAINING_ROOT = Path(__file__).resolve().parents[1]
MERGED_VAL = TRAINING_ROOT / "data" / "merged_dataset" / "val"
OUT_ROOT = TRAINING_ROOT / "data" / "evalsets" / "val_old_scheme"
OLD_MODEL = TRAINING_ROOT.parent / "models" / "best_int8.tflite"

# 기존 모델 실측 클래스 순서 (debug_class_order.py로 검증됨): 0=white_cane, 1=person
OLD_WHITE_CANE, OLD_PERSON = 0, 1
REMAP = {TARGET_PERSON: OLD_PERSON, TARGET_WHITE_CANE: OLD_WHITE_CANE}  # wheelchair(2)는 제외


def build_eval_set() -> None:
    img_out = OUT_ROOT / "images"
    lbl_out = OUT_ROOT / "labels"
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    src_img_dir = MERGED_VAL / "images"
    src_lbl_dir = MERGED_VAL / "labels"

    for img_path in src_img_dir.iterdir():
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        dst_img = img_out / img_path.name
        if not dst_img.exists():
            os.link(img_path, dst_img)  # 하드링크 (같은 볼륨, 용량 절약)

        lbl_path = src_lbl_dir / (img_path.stem + ".txt")
        boxes = read_yolo_labels(lbl_path)
        remapped = [(REMAP[cls], cx, cy, w, h) for cls, cx, cy, w, h in boxes if cls in REMAP]
        write_yolo_labels(lbl_out / (img_path.stem + ".txt"), remapped)

    data_yaml = OUT_ROOT / "data.yaml"
    data_yaml.write_text(
        "path: " + str(OUT_ROOT).replace("\\", "/") + "\n"
        "train: images\n"
        "val: images\n"
        "nc: 2\n"
        "names: ['white_cane', 'person']\n",
        encoding="utf-8",
    )
    print(f"eval set ready: {data_yaml}")


def main() -> None:
    build_eval_set()
    model = YOLO(str(OLD_MODEL))
    metrics = model.val(data=str(OUT_ROOT / "data.yaml"), imgsz=320, split="val")
    print("\n=== 기존 best_int8.tflite 검증 결과 (person/white_cane) ===")
    print(metrics.box.maps)  # per-class mAP50-95
    print("mAP50:", metrics.box.map50)
    print("mAP50-95:", metrics.box.map)


if __name__ == "__main__":
    main()
