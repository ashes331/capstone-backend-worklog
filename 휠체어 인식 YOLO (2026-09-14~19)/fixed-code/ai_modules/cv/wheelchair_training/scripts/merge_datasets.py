"""visionguide_dataset + pseudo-labeled wheelchair 데이터셋을 최종 스킴으로 병합.

최종 클래스: person=0, white_cane=1, wheelchair=2 (common.TARGET_CLASSES)

- visionguide_dataset: 원본 클래스 [white_cane=0, person=1] -> 리매핑 필요
- wheelchair_pseudo_labeled: pseudo_label_wheelchair.py가 이미 최종 스킴으로 출력해둠 -> 그대로 복사

파일명 충돌 방지를 위해 출처별 접두사(vg_/wc_)를 붙여 복사한다.
"""
from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

from common import TARGET_CLASSES, read_yolo_labels, write_yolo_labels

HERE = Path(__file__).resolve()
TRAINING_ROOT = HERE.parents[1]  # ai_modules/cv/wheelchair_training
VG_ROOT = Path(r"C:\Users\SAMSUNG\Downloads\visionguide_dataset\datasets")
WC_ROOT = TRAINING_ROOT / "data" / "wheelchair_pseudo_labeled"
OUT_ROOT = TRAINING_ROOT / "data" / "merged_dataset"

# visionguide_dataset 원본 클래스 순서 (data.yaml: ['white_cane', 'person'])
VG_WHITE_CANE, VG_PERSON = 0, 1
VG_REMAP = {VG_WHITE_CANE: 1, VG_PERSON: 0}  # -> target white_cane=1, person=0

VG_SPLIT_MAP = {"train": "train", "val": "val", "test": "test"}
WC_SPLIT_MAP = {"train": "train", "valid": "val"}  # wheelchair 데이터셋엔 test 없음


def copy_split(
    src_img_dir: Path,
    src_lbl_dir: Path,
    out_split: str,
    prefix: str,
    remap: dict[int, int] | None,
    counter: Counter,
) -> None:
    if not src_img_dir.exists():
        return
    out_img_dir = OUT_ROOT / out_split / "images"
    out_lbl_dir = OUT_ROOT / out_split / "labels"
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    for img_path in src_img_dir.iterdir():
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        lbl_path = src_lbl_dir / (img_path.stem + ".txt")
        boxes = read_yolo_labels(lbl_path)
        if remap is not None:
            boxes = [(remap[cls], cx, cy, w, h) for cls, cx, cy, w, h in boxes if cls in remap]

        new_name = f"{prefix}_{img_path.name}"
        shutil.copy2(img_path, out_img_dir / new_name)
        write_yolo_labels(out_lbl_dir / (Path(new_name).stem + ".txt"), boxes)

        for cls, *_ in boxes:
            counter[(out_split, cls)] += 1


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    counter: Counter = Counter()

    for vg_split, out_split in VG_SPLIT_MAP.items():
        copy_split(
            VG_ROOT / vg_split / "images",
            VG_ROOT / vg_split / "labels",
            out_split,
            prefix="vg",
            remap=VG_REMAP,
            counter=counter,
        )
        print(f"visionguide[{vg_split}] -> {out_split} done")

    for wc_split, out_split in WC_SPLIT_MAP.items():
        copy_split(
            WC_ROOT / wc_split / "images",
            WC_ROOT / wc_split / "labels",
            out_split,
            prefix="wc",
            remap=None,  # 이미 최종 스킴
            counter=counter,
        )
        print(f"wheelchair[{wc_split}] -> {out_split} done")

    data_yaml = OUT_ROOT / "data.yaml"
    data_yaml.write_text(
        "path: " + str(OUT_ROOT).replace("\\", "/") + "\n"
        "train: train/images\n"
        "val: val/images\n"
        "test: test/images\n"
        f"nc: {len(TARGET_CLASSES)}\n"
        f"names: {TARGET_CLASSES}\n",
        encoding="utf-8",
    )
    print(f"\ndata.yaml written: {data_yaml}")

    print("\n=== 클래스 분포 (split x class) ===")
    for split in ("train", "val", "test"):
        row = [f"{TARGET_CLASSES[c]}={counter[(split, c)]}" for c in range(len(TARGET_CLASSES))]
        print(f"{split}: " + ", ".join(row))


if __name__ == "__main__":
    main()
