"""visionguide_dataset 정답 박스 위치에서 모델이 실제 어느 class index로 반응하는지
전체 데이터셋에 걸쳐 통계적으로 집계 -> tflite 모델의 0/1 클래스 순서를 검증한다."""
from pathlib import Path
import cv2
import numpy as np
from common import read_yolo_labels, cxcywh_norm_to_xyxy_px, iou_xyxy
from tflite_person_detector import TFLitePersonDetector

VG_ROOT = Path(r"C:\Users\SAMSUNG\Downloads\visionguide_dataset\datasets\train")
SRC_WHITE_CANE, SRC_PERSON = 0, 1  # data.yaml: ['white_cane', 'person']

d = TFLitePersonDetector()

# 정답 박스 위치와 겹치는 모델 anchor들 중 class0/class1 평균 점수를 라벨 종류별로 집계
agg = {SRC_WHITE_CANE: {"class0": [], "class1": []}, SRC_PERSON: {"class0": [], "class1": []}}

import random
label_files = sorted((VG_ROOT / "labels").glob("*.txt"))
random.seed(0)
random.shuffle(label_files)
print(f"total label files: {len(label_files)}")

gt_counts = {SRC_WHITE_CANE: 0, SRC_PERSON: 0}

for i, lbl_path in enumerate(label_files):
    if i >= 300:  # 표본 300장 (랜덤)
        break
    boxes = read_yolo_labels(lbl_path)
    if not boxes:
        continue
    img_path = VG_ROOT / "images" / (lbl_path.stem + ".jpg")
    if not img_path.exists():
        continue
    img = cv2.imread(str(img_path))
    if img is None:
        continue
    img_h, img_w = img.shape[:2]

    data = d._preprocess(img)
    d.interpreter.set_tensor(d._in["index"], data)
    d.interpreter.invoke()
    raw = d.interpreter.get_tensor(d._out["index"])
    out_scale, out_zero = d._out["quantization"]
    raw = (raw.astype(np.float32) - out_zero) * out_scale
    out = raw[0]
    if out.shape[0] < out.shape[1]:
        out = np.transpose(out)
    anchor_boxes_cxcywh = out[:, :4]
    scores = out[:, 4:]

    anchor_xyxy = []
    for cx, cy, w, h in anchor_boxes_cxcywh:
        x1 = (cx - w / 2) * img_w
        y1 = (cy - h / 2) * img_h
        x2 = (cx + w / 2) * img_w
        y2 = (cy + h / 2) * img_h
        anchor_xyxy.append((x1, y1, x2, y2))

    for cls, cx, cy, w, h in boxes:
        if cls not in (SRC_WHITE_CANE, SRC_PERSON):
            continue
        gt_counts[cls] += 1
        gt_box = cxcywh_norm_to_xyxy_px((cx, cy, w, h), img_w, img_h)
        best_iou, best_idx = 0.0, -1
        for idx, abox in enumerate(anchor_xyxy):
            iou = iou_xyxy(gt_box, abox)
            if iou > best_iou:
                best_iou, best_idx = iou, idx
        if best_idx >= 0 and best_iou > 0.3:
            agg[cls]["class0"].append(float(scores[best_idx, 0]))
            agg[cls]["class1"].append(float(scores[best_idx, 1]))

print("gt_counts:", gt_counts)
for cls, label in [(SRC_WHITE_CANE, "white_cane(GT)"), (SRC_PERSON, "person(GT)")]:
    c0 = agg[cls]["class0"]
    c1 = agg[cls]["class1"]
    if c0:
        print(f"{label}: n={len(c0)}  model_class0_mean={np.mean(c0):.3f}  model_class1_mean={np.mean(c1):.3f}")
    else:
        print(f"{label}: no matches found")
