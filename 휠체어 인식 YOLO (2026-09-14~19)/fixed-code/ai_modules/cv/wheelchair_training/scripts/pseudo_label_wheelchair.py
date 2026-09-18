"""wheelchair.v5i.yolov8 데이터셋 pseudo-labeling (작업계획서 9/16 단계).

문제: 원본 데이터셋의 'people_wheelchair' 클래스는 사람+휠체어를 통째로 감싸는
      느슨한 박스라서 그대로 'person'으로 쓰면 person bbox 정밀도가 떨어진다.
해결: 기존 person/white_cane 탐지 모델(best_int8.tflite)로 각 이미지를 추론해
      'people_wheelchair' 영역과 겹치는 타이트한 person 박스를 새로 뽑아 대체한다.
      모델이 못 찾으면 원본 느슨한 박스를 폴백으로 쓰고 검수 로그에 남긴다.

출력 클래스 스킴: person=0, white_cane=1, wheelchair=2 (원본 white_cane 라벨은 없음)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import (
    TARGET_PERSON,
    TARGET_WHEELCHAIR,
    cxcywh_norm_to_xyxy_px,
    iou_xyxy,
    read_yolo_labels,
    write_yolo_labels,
    xyxy_px_to_cxcywh_norm,
)
from PIL import Image
from tflite_person_detector import TFLitePersonDetector

# 원본 wheelchair.v5i.yolov8 data.yaml 클래스 순서
SRC_PEOPLE_WHEELCHAIR, SRC_PERSON, SRC_WHEELCHAIR = 0, 1, 2

DEDUPE_IOU = 0.5   # 이미 라벨된 person과 겹치면 중복으로 간주
RESOLVE_IOU = 0.3  # people_wheelchair 박스와 겹치면 그 인스턴스를 해결한 것으로 간주


def process_split(
    src_root: Path,
    dst_root: Path,
    split: str,
    detector: TFLitePersonDetector,
    conf_threshold: float,
) -> dict:
    img_dir = src_root / split / "images"
    lbl_dir = src_root / split / "labels"
    out_img_dir = dst_root / split / "images"
    out_lbl_dir = dst_root / split / "labels"
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    stats = {"images": 0, "pw_total": 0, "pw_resolved": 0, "pw_fallback": 0, "review": []}

    if not img_dir.exists():
        return stats

    for img_path in sorted(img_dir.iterdir()):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        stats["images"] += 1
        lbl_path = lbl_dir / (img_path.stem + ".txt")
        src_boxes = read_yolo_labels(lbl_path)

        with Image.open(img_path) as im:
            img_w, img_h = im.size

        person_px = [
            cxcywh_norm_to_xyxy_px((cx, cy, w, h), img_w, img_h)
            for cls, cx, cy, w, h in src_boxes
            if cls == SRC_PERSON
        ]
        wheelchair_px = [
            cxcywh_norm_to_xyxy_px((cx, cy, w, h), img_w, img_h)
            for cls, cx, cy, w, h in src_boxes
            if cls == SRC_WHEELCHAIR
        ]
        pw_px = [
            cxcywh_norm_to_xyxy_px((cx, cy, w, h), img_w, img_h)
            for cls, cx, cy, w, h in src_boxes
            if cls == SRC_PEOPLE_WHEELCHAIR
        ]

        resolved_px: list[tuple[float, float, float, float]] = []
        if pw_px:
            stats["pw_total"] += len(pw_px)
            detections = detector.detect_persons(img_path, conf_threshold=conf_threshold)
            resolved_flags = [False] * len(pw_px)

            for conf, box in detections:
                if any(iou_xyxy(box, p) > DEDUPE_IOU for p in person_px):
                    continue  # 이미 라벨된 person과 중복
                best_j, best_iou = -1, 0.0
                for j, pw in enumerate(pw_px):
                    iou = iou_xyxy(box, pw)
                    if iou > best_iou:
                        best_iou, best_j = iou, j
                if best_j >= 0 and best_iou > RESOLVE_IOU:
                    resolved_px.append(box)
                    resolved_flags[best_j] = True

            for j, ok in enumerate(resolved_flags):
                if ok:
                    stats["pw_resolved"] += 1
                else:
                    stats["pw_fallback"] += 1
                    stats["review"].append(f"{split}/{img_path.name}")
                    resolved_px.append(pw_px[j])  # 폴백: 원본 느슨한 박스 유지

            # people_wheelchair 인스턴스는 원본 데이터셋에 대응하는 wheelchair 박스가
            # 거의 없음(496/498장) -> person과 별개로 원본 느슨한 박스를 wheelchair로도 추가.
            # 그래야 "사람이 탄 휠체어" 장면이 wheelchair 클래스 학습에 실제로 반영됨.
            wheelchair_px = wheelchair_px + pw_px

        out_boxes = []
        for x1, y1, x2, y2 in person_px + resolved_px:
            cx, cy, w, h = xyxy_px_to_cxcywh_norm((x1, y1, x2, y2), img_w, img_h)
            out_boxes.append((TARGET_PERSON, cx, cy, w, h))
        for x1, y1, x2, y2 in wheelchair_px:
            cx, cy, w, h = xyxy_px_to_cxcywh_norm((x1, y1, x2, y2), img_w, img_h)
            out_boxes.append((TARGET_WHEELCHAIR, cx, cy, w, h))

        write_yolo_labels(out_lbl_dir / (img_path.stem + ".txt"), out_boxes)
        shutil.copy2(img_path, out_img_dir / img_path.name)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default=r"C:\Users\SAMSUNG\Downloads\wheelchair.v5i.yolov8")
    parser.add_argument(
        "--dst",
        default=str(Path(__file__).resolve().parents[1] / "data" / "wheelchair_pseudo_labeled"),
    )
    parser.add_argument("--conf", type=float, default=0.5)
    args = parser.parse_args()

    src_root = Path(args.src)
    dst_root = Path(args.dst)
    detector = TFLitePersonDetector()

    total = {"images": 0, "pw_total": 0, "pw_resolved": 0, "pw_fallback": 0, "review": []}
    for split in ("train", "valid", "test"):
        stats = process_split(src_root, dst_root, split, detector, args.conf)
        print(f"[{split}] images={stats['images']} pw_total={stats['pw_total']} "
              f"resolved={stats['pw_resolved']} fallback={stats['pw_fallback']}")
        for k in ("images", "pw_total", "pw_resolved", "pw_fallback"):
            total[k] += stats[k]
        total["review"].extend(stats["review"])

    print(f"\n=== TOTAL === images={total['images']} pw_total={total['pw_total']} "
          f"resolved={total['pw_resolved']} fallback={total['pw_fallback']}")

    review_path = dst_root / "review_log.txt"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("\n".join(total["review"]), encoding="utf-8")
    print(f"폴백(수동 검수 필요) 목록: {review_path} ({len(total['review'])}건)")


if __name__ == "__main__":
    main()
