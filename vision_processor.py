"""Low-cost computer-vision simulation with optional local YOLOv8n support."""

from __future__ import annotations

import base64
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from config import get_settings
from models import DetectedObject, VisionResult


def generate_mock_frame(width: int = 960, height: int = 540, cycle: int = 0) -> np.ndarray:
    """Create a CCTV-like street frame without downloading a video asset."""

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[: int(height * 0.58)] = (116, 128, 145)  # overcast sky
    frame[int(height * 0.58) :] = (62, 64, 58)  # road

    # Buildings and windows provide enough texture for a convincing dashboard.
    buildings = ((0, 100, 170, 315), (185, 55, 370, 315), (720, 80, 960, 315))
    for left, top, right, bottom in buildings:
        cv2.rectangle(frame, (left, top), (right, bottom), (45, 48, 55), -1)
        for x in range(left + 18, right - 8, 36):
            for y in range(top + 20, bottom - 8, 42):
                cv2.rectangle(frame, (x, y), (x + 13, y + 16), (173, 157, 93), -1)

    waterline = int(height * (0.61 - 0.055 * math.sin(cycle / 2.0)))
    cv2.line(frame, (0, waterline), (width, waterline), (180, 210, 230), 2)

    # Cars are intentionally below the waterline so the detector can explain
    # why the depth score is escalating.
    for x, y, scale in ((155, 348, 1.0), (430, 326, 0.92), (684, 362, 1.12)):
        body_w = int(142 * scale)
        body_h = int(52 * scale)
        cv2.rectangle(frame, (x, y), (x + body_w, y + body_h), (55, 75, 95), -1)
        cv2.rectangle(frame, (x + 25, y - 24), (x + body_w - 28, y), (70, 84, 101), -1)
        cv2.circle(frame, (x + 28, y + body_h), int(14 * scale), (21, 22, 23), -1)
        cv2.circle(frame, (x + body_w - 28, y + body_h), int(14 * scale), (21, 22, 23), -1)

    return frame


def _encode_frame(frame: np.ndarray) -> str:
    success, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not success:
        raise RuntimeError("OpenCV could not encode the annotated CCTV frame")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _local_yolo_objects(frame: np.ndarray, model_path: str) -> list[DetectedObject]:
    """Run YOLO only when an already-downloaded local weight exists."""

    if not Path(model_path).is_file():
        return []
    try:
        from ultralytics import YOLO  # imported lazily to keep fallback startup fast

        model = YOLO(model_path)
        results = model.predict(frame, verbose=False, conf=0.25, imgsz=640)
    except Exception:
        # A missing native runtime or incompatible model must not break the
        # command center; the OpenCV simulation remains the source of truth.
        return []

    objects: list[DetectedObject] = []
    vehicle_labels = {"car", "truck", "bus", "motorcycle"}
    for result in results:
        names: dict[int, str] = getattr(result, "names", {})
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            class_id = int(box.cls[0].item())
            label = names.get(class_id, str(class_id))
            if label not in vehicle_labels:
                continue
            coordinates = [int(value) for value in box.xyxy[0].tolist()]
            confidence = float(box.conf[0].item())
            objects.append(DetectedObject(label=label, confidence=confidence, box=coordinates))
    return objects


def analyze_frame(
    frame: np.ndarray | None = None,
    *,
    cycle: int = 0,
    use_yolo: bool | None = None,
    model_path: str | None = None,
) -> VisionResult:
    """Annotate a frame and estimate flood depth in centimeters.

    The OpenCV water mask is deliberately deterministic and is always used for
    the depth estimate. YOLO, when available, contributes optional vehicle
    detections and never becomes a required network dependency.
    """

    settings = get_settings()
    source_frame = frame.copy() if frame is not None else generate_mock_frame(cycle=cycle)
    if source_frame.ndim != 3 or source_frame.shape[2] != 3:
        raise ValueError("frame must be a color image with shape (height, width, 3)")

    height, width = source_frame.shape[:2]
    annotated = source_frame.copy()
    waterline = int(height * (0.61 - 0.055 * math.sin(cycle / 2.0)))
    waterline = max(int(height * 0.42), min(int(height * 0.78), waterline))

    mask = np.zeros((height, width), dtype=np.uint8)
    mask[waterline:, :] = 255
    blue_layer = np.zeros_like(annotated)
    blue_layer[:, :] = (185, 105, 38)
    annotated[mask > 0] = cv2.addWeighted(annotated[mask > 0], 0.58, blue_layer[mask > 0], 0.42, 0)
    cv2.line(annotated, (0, waterline), (width, waterline), (255, 235, 130), 3)
    cv2.putText(
        annotated,
        f"SIMULATED WATERLINE  |  {max(1, int((height - waterline) / height * 220))} cm",
        (22, max(32, waterline - 16)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (240, 248, 255),
        2,
        cv2.LINE_AA,
    )

    # Measurement grid makes the depth estimate legible in the UI.
    for y in range(waterline + 20, height, 28):
        cv2.line(annotated, (0, y), (width, y), (196, 215, 230), 1)
    for x in range(0, width, 80):
        cv2.line(annotated, (x, waterline), (x, height), (196, 215, 230), 1)

    simulated_boxes = [
        [155, 324, 297, 400],
        [430, 303, 561, 374],
        [684, 333, 843, 420],
    ]
    yolo_objects = _local_yolo_objects(source_frame, model_path or settings.yolo_model_path) if (use_yolo if use_yolo is not None else settings.enable_yolo) else []
    if yolo_objects:
        objects = [item.model_copy(update={"flooded": item.box[3] >= waterline}) for item in yolo_objects]
    else:
        objects = [
        DetectedObject(
            label="flooded car",
            confidence=0.94 - index * 0.04,
            flooded=box[3] >= waterline,
            box=box,
        )
        for index, box in enumerate(simulated_boxes)
        ]
    for detected in objects:
        left, top, right, bottom = detected.box
        color = (36, 62, 244) if detected.flooded else (30, 190, 240)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 3)
        label = f"{detected.label} {detected.confidence:.0%}"
        cv2.rectangle(annotated, (left, max(0, top - 26)), (left + 170, top), color, -1)
        cv2.putText(annotated, label, (left + 6, max(18, top - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

    depth_cm = max(1, min(500, int((height - waterline) / height * 220)))
    return VisionResult(
        flooding_depth_cm=depth_cm,
        waterline_px=waterline,
        water_mask_ratio=float(np.count_nonzero(mask)) / float(mask.size),
        detected_objects=objects,
        annotated_frame_base64=_encode_frame(annotated),
        frame_width=width,
        frame_height=height,
        detector_mode="yolov8n" if yolo_objects else "opencv-simulation",
    )


def decode_frame(encoded: str) -> np.ndarray:
    """Decode a base64 JPEG for callers that want to inspect an annotation."""

    raw = base64.b64decode(encoded)
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("encoded frame is not a valid image")
    return image
