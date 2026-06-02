"""Pretrained Mask R-CNN inference over street imagery.

Uses torchvision's COCO-trained weights — no fine-tuning. The point is to show
the shape of a detection step, not to claim accuracy on road defects.
COCO class 13 = stop sign, 10 = traffic light, 3 = car, 8 = truck. Widen
``keep_classes`` to taste.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import torch
from PIL import Image
from torchvision.models.detection import (
    MaskRCNN_ResNet50_FPN_Weights,
    maskrcnn_resnet50_fpn,
)
from torchvision.transforms.functional import to_tensor


@dataclass(slots=True)
class Detection:
    label: str
    score: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2


@lru_cache(maxsize=1)
def _load_model() -> tuple[torch.nn.Module, list[str]]:
    weights = MaskRCNN_ResNet50_FPN_Weights.COCO_V1
    model = maskrcnn_resnet50_fpn(weights=weights).eval()
    return model, weights.meta["categories"]


@lru_cache(maxsize=4)
def _load_yolo(weights_path: str):
    from ultralytics import YOLO  # lazy import; only needed for the yolo path
    return YOLO(weights_path)


def detect_yolo(
    image_path: Path,
    weights_path: Path,
    *,
    score_threshold: float = 0.3,
) -> list[Detection]:
    """RDD2022 fine-tuned YOLO inference. Returns RDD2022 labels (D00/D10/D20/D40)."""
    model = _load_yolo(str(weights_path))
    result = model(str(image_path), conf=score_threshold, verbose=False)[0]
    names = result.names
    detections: list[Detection] = []
    for box in result.boxes:
        cls = int(box.cls.item())
        score = float(box.conf.item())
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append(
            Detection(label=names[cls], score=score, bbox=(x1, y1, x2, y2))
        )
    return detections


def detect(
    image_path: Path,
    *,
    score_threshold: float = 0.5,
    keep_classes: frozenset[str] | None = None,
) -> list[Detection]:
    model, categories = _load_model()
    image = Image.open(image_path).convert("RGB")
    tensor = to_tensor(image).unsqueeze(0)

    with torch.inference_mode():
        output = model(tensor)[0]

    detections: list[Detection] = []
    for label_idx, score, box in zip(
        output["labels"].tolist(),
        output["scores"].tolist(),
        output["boxes"].tolist(),
        strict=True,
    ):
        if score < score_threshold:
            continue
        label = categories[label_idx]
        if keep_classes is not None and label not in keep_classes:
            continue
        detections.append(Detection(label=label, score=score, bbox=tuple(box)))
    return detections
