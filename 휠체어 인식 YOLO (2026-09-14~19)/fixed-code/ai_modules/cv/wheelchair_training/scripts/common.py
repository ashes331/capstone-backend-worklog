"""YOLO 라벨 IO 및 박스 유틸 - pseudo-labeling/병합 스크립트 공용."""
from __future__ import annotations

from pathlib import Path

# 최종 병합 클래스 스킴 (작업계획서 4단계 기준)
TARGET_CLASSES = ["person", "white_cane", "wheelchair"]
TARGET_PERSON, TARGET_WHITE_CANE, TARGET_WHEELCHAIR = 0, 1, 2


def read_yolo_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    if not path.exists():
        return []
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        cls = int(parts[0])
        cx, cy, w, h = (float(x) for x in parts[1:5])
        boxes.append((cls, cx, cy, w, h))
    return boxes


def write_yolo_labels(path: Path, boxes: list[tuple[int, float, float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cls, cx, cy, w, h in boxes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def cxcywh_norm_to_xyxy_px(box: tuple[float, float, float, float], img_w: int, img_h: int) -> tuple[float, float, float, float]:
    cx, cy, w, h = box
    x1 = (cx - w / 2) * img_w
    y1 = (cy - h / 2) * img_h
    x2 = (cx + w / 2) * img_w
    y2 = (cy + h / 2) * img_h
    return x1, y1, x2, y2


def xyxy_px_to_cxcywh_norm(box: tuple[float, float, float, float], img_w: int, img_h: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2 / img_w
    cy = (y1 + y2) / 2 / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    return cx, cy, w, h


def iou_xyxy(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0
