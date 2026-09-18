"""merged_dataset/train에서 wheelchair(class 2)가 포함된 이미지를 N배 복제해
클래스 불균형(train 기준 person:wheelchair = 67:1)을 완화한다."""
from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

from common import TARGET_WHEELCHAIR, read_yolo_labels

TRAIN_DIR = Path(__file__).resolve().parents[1] / "data" / "merged_dataset" / "train"
EXTRA_COPIES = 2  # 원본 1 + 복제 2 = 총 3배 노출


def main() -> None:
    img_dir = TRAIN_DIR / "images"
    lbl_dir = TRAIN_DIR / "labels"

    targets = []
    for lbl_path in lbl_dir.glob("*.txt"):
        boxes = read_yolo_labels(lbl_path)
        if any(cls == TARGET_WHEELCHAIR for cls, *_ in boxes):
            targets.append(lbl_path.stem)

    print(f"wheelchair 포함 이미지: {len(targets)}장 -> 각 {EXTRA_COPIES}회 복제")

    for stem in targets:
        img_candidates = list(img_dir.glob(stem + ".*"))
        if not img_candidates:
            continue
        img_path = img_candidates[0]
        lbl_path = lbl_dir / (stem + ".txt")
        for i in range(1, EXTRA_COPIES + 1):
            new_stem = f"{stem}_dup{i}"
            shutil.copy2(img_path, img_dir / f"{new_stem}{img_path.suffix}")
            shutil.copy2(lbl_path, lbl_dir / f"{new_stem}.txt")

    counter: Counter = Counter()
    for lbl_path in lbl_dir.glob("*.txt"):
        for cls, *_ in read_yolo_labels(lbl_path):
            counter[cls] += 1
    print("오버샘플링 후 train 클래스 분포:", dict(counter))


if __name__ == "__main__":
    main()
