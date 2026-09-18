"""pseudo-labeling 결과 검수용: 라벨 박스를 이미지에 그려서 저장.

클래스별 색상: person=초록, white_cane=파랑, wheelchair=빨강
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
from common import cxcywh_norm_to_xyxy_px, read_yolo_labels

COLORS = {0: (0, 200, 0), 1: (255, 0, 0), 2: (0, 0, 255)}  # BGR
NAMES = {0: "person", 1: "white_cane", 2: "wheelchair"}


def draw_and_save(img_path: Path, lbl_path: Path, out_path: Path) -> None:
    img = cv2.imread(str(img_path))
    if img is None:
        return
    h, w = img.shape[:2]
    for cls, cx, cy, bw, bh in read_yolo_labels(lbl_path):
        x1, y1, x2, y2 = cxcywh_norm_to_xyxy_px((cx, cy, bw, bh), w, h)
        color = COLORS.get(cls, (255, 255, 255))
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)
        cv2.putText(img, NAMES.get(cls, str(cls)), (int(x1), max(0, int(y1) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(Path(__file__).resolve().parents[1] / "data" / "wheelchair_pseudo_labeled"))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data" / "review_samples"))
    parser.add_argument("--n_resolved", type=int, default=12)
    parser.add_argument("--n_fallback", type=int, default=6)
    args = parser.parse_args()

    data_root = Path(args.data)
    out_root = Path(args.out)
    review_log = (data_root / "review_log.txt").read_text(encoding="utf-8").splitlines()
    fallback_set = set(review_log)

    random.seed(1)
    all_pairs = []
    for split in ("train", "valid"):
        img_dir = data_root / split / "images"
        if not img_dir.exists():
            continue
        for img_path in img_dir.iterdir():
            key = f"{split}/{img_path.name}"
            lbl_path = data_root / split / "labels" / (img_path.stem + ".txt")
            all_pairs.append((key, img_path, lbl_path))

    fallback_pairs = [p for p in all_pairs if p[0] in fallback_set]
    resolved_pairs = [p for p in all_pairs if p[0] not in fallback_set]

    sample_fallback = random.sample(fallback_pairs, min(args.n_fallback, len(fallback_pairs)))
    sample_resolved = random.sample(resolved_pairs, min(args.n_resolved, len(resolved_pairs)))

    for tag, samples in [("resolved", sample_resolved), ("fallback", sample_fallback)]:
        for key, img_path, lbl_path in samples:
            safe_name = key.replace("/", "_")
            draw_and_save(img_path, lbl_path, out_root / f"{tag}__{safe_name}")

    print(f"resolved samples: {len(sample_resolved)}, fallback samples: {len(sample_fallback)}")
    print(f"saved to: {out_root}")


if __name__ == "__main__":
    main()
