"""기존 best_int8.tflite(person=0, white_cane=1)로 이미지 내 모든 박스를 탐지.

approach_detector.py의 전처리/양자화 로직을 재사용하되, "흰 지팡이 존재 여부"만 보는
대신 NMS까지 포함한 전체 박스 리스트를 반환한다 (pseudo-labeling용).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

try:
    import tflite_runtime.interpreter as _tflite
except ImportError:
    import tensorflow as tf  # type: ignore
    _tflite = tf.lite  # type: ignore

MODEL_PATH = Path(__file__).resolve().parents[1] / "base_model" / "original_person_cane_int8.tflite"
PERSON_CLASS_ID = 1  # 재학습 전 원본(2클래스) 모델 기준 검증된 클래스 순서: 0=white_cane, 1=person
# 주의: ai_modules/cv/models/best_int8.tflite는 재학습 후 3클래스 모델로 교체됐으므로
# pseudo-labeling(재학습용 person 부트스트랩)은 반드시 이 base_model 사본을 써야 함


class TFLitePersonDetector:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.interpreter = _tflite.Interpreter(model_path=str(model_path))
        self.interpreter.allocate_tensors()
        self._in = self.interpreter.get_input_details()[0]
        self._out = self.interpreter.get_output_details()[0]
        shape = self._in["shape"]
        self._h, self._w = int(shape[1]), int(shape[2])
        self._dtype = self._in["dtype"]
        self._in_scale, self._in_zero = self._in["quantization"]

    def _preprocess(self, img_bgr: np.ndarray) -> np.ndarray:
        img = cv2.resize(img_bgr, (self._w, self._h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self._dtype == np.int8:
            f = img.astype(np.float32) / 255.0
            if self._in_scale != 0.0:
                q = (f / self._in_scale + self._in_zero).astype(np.int8)
            else:
                q = (img.astype(np.int32) - 128).astype(np.int8)
            return np.expand_dims(q, axis=0)
        return np.expand_dims(img.astype(np.float32) / 255.0, axis=0)

    def detect_persons(
        self,
        img_path: Path,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
    ) -> list[tuple[float, tuple[float, float, float, float]]]:
        """반환: [(confidence, (x1,y1,x2,y2))] - 좌표는 원본 이미지 픽셀 기준."""
        img = cv2.imread(str(img_path))
        if img is None:
            return []
        img_h, img_w = img.shape[:2]

        data = self._preprocess(img)
        self.interpreter.set_tensor(self._in["index"], data)
        self.interpreter.invoke()
        raw = self.interpreter.get_tensor(self._out["index"])

        out_scale, out_zero = self._out["quantization"]
        if self._out["dtype"] == np.int8:
            raw = (raw.astype(np.float32) - out_zero) * out_scale
        out = raw[0]
        if out.shape[0] < out.shape[1]:
            out = np.transpose(out)  # -> (num_anchors, 4+num_classes)

        boxes_cxcywh = out[:, :4]  # 정규화된 [0,1] 좌표 (입력 해상도와 무관)
        scores = out[:, 4:]
        if scores.size == 0:
            return []

        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)

        person_mask = (class_ids == PERSON_CLASS_ID) & (confidences > conf_threshold)
        if not np.any(person_mask):
            return []

        boxes = boxes_cxcywh[person_mask]
        confs = confidences[person_mask]

        # 정규화 좌표 -> 원본 이미지 픽셀 스케일
        xywh_for_nms = []
        for cx, cy, w, h in boxes:
            x1 = (cx - w / 2) * img_w
            y1 = (cy - h / 2) * img_h
            bw = w * img_w
            bh = h * img_h
            xywh_for_nms.append([x1, y1, bw, bh])

        indices = cv2.dnn.NMSBoxes(xywh_for_nms, confs.tolist(), conf_threshold, iou_threshold)
        if len(indices) == 0:
            return []
        indices = np.array(indices).flatten()

        results = []
        for i in indices:
            x1, y1, bw, bh = xywh_for_nms[i]
            results.append((float(confs[i]), (x1, y1, x1 + bw, y1 + bh)))
        return results
