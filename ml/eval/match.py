"""IoU-based matcher: predictions ⟷ ground-truth labels.

A single class, per-image matching used both by:
  - per-marker UI labelling (TP / FP for predictions, FN for missed labels), and
  - the calibration set (each prediction tagged TP or FP, fed into reliability
    bins).

Matching is greedy by descending score, IoU ≥ ``iou_threshold``, predictions
restricted to the same class as the label. That matches the COCO/PASCAL eval
convention used to compute mAP — so the precision / recall we read off here
line up with the mAP numbers from ultralytics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CLASS_NAMES = ["D00", "D10", "D20", "D40"]
CLASS_INDEX = {n: i for i, n in enumerate(CLASS_NAMES)}


@dataclass(slots=True)
class Box:
    cls: str
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(slots=True)
class Prediction:
    cls: str
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    # set during matching
    match: str = "unmatched"  # "tp" | "fp"
    matched_label_idx: int | None = None


def iou(a: Box | Prediction, b: Box | Prediction) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def parse_yolo_labels(path: Path, width: int, height: int) -> list[Box]:
    """YOLO label format: ``cls cx cy w h`` all normalized to [0, 1]."""
    boxes: list[Box] = []
    if not path.exists():
        return boxes
    for line in path.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls_idx = int(parts[0])
        cx, cy, w, h = (float(x) for x in parts[1:])
        x1 = (cx - w / 2) * width
        y1 = (cy - h / 2) * height
        x2 = (cx + w / 2) * width
        y2 = (cy + h / 2) * height
        boxes.append(Box(cls=CLASS_NAMES[cls_idx], x1=x1, y1=y1, x2=x2, y2=y2))
    return boxes


@dataclass(slots=True)
class MatchResult:
    predictions: list[Prediction]
    labels: list[Box]
    matched_label_indices: set[int]

    @property
    def false_negatives(self) -> list[Box]:
        return [b for i, b in enumerate(self.labels) if i not in self.matched_label_indices]

    @property
    def tp_count(self) -> int:
        return sum(1 for p in self.predictions if p.match == "tp")

    @property
    def fp_count(self) -> int:
        return sum(1 for p in self.predictions if p.match == "fp")

    @property
    def fn_count(self) -> int:
        return len(self.labels) - len(self.matched_label_indices)


def match_predictions(
    predictions: Iterable[Prediction],
    labels: list[Box],
    iou_threshold: float = 0.5,
) -> MatchResult:
    """Greedy match: descending score, same class, IoU ≥ threshold.

    Each prediction can claim at most one label; each label at most one prediction.
    Mutates the ``Prediction`` objects in place (sets .match and .matched_label_idx).
    Returns the matched set for FN computation.
    """
    preds_sorted = sorted(predictions, key=lambda p: p.score, reverse=True)
    used_labels: set[int] = set()
    for pred in preds_sorted:
        best_idx = -1
        best_iou = iou_threshold
        for i, lbl in enumerate(labels):
            if i in used_labels:
                continue
            if lbl.cls != pred.cls:
                continue
            v = iou(pred, lbl)
            if v >= best_iou:
                best_iou = v
                best_idx = i
        if best_idx >= 0:
            pred.match = "tp"
            pred.matched_label_idx = best_idx
            used_labels.add(best_idx)
        else:
            pred.match = "fp"
    return MatchResult(
        predictions=list(preds_sorted),
        labels=labels,
        matched_label_indices=used_labels,
    )


# --- quick sanity check when run directly ---------------------------------


def _self_test() -> None:
    preds = [
        Prediction("D00", 10, 10, 50, 50, score=0.9),
        Prediction("D00", 12, 12, 52, 52, score=0.8),  # overlaps with first
        Prediction("D40", 200, 200, 250, 250, score=0.7),  # wrong class for any label
    ]
    labels = [
        Box("D00", 10, 10, 50, 50),
        Box("D20", 100, 100, 130, 130),  # nothing predicts D20
    ]
    res = match_predictions(preds, labels, iou_threshold=0.5)
    assert res.tp_count == 1, res.tp_count
    assert res.fp_count == 2, res.fp_count
    assert res.fn_count == 1, res.fn_count
    print("match.py self-test ok")


if __name__ == "__main__":
    _self_test()
