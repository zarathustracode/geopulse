"""Temperature scaling on the full RDD2022 test set.

Pipeline:
  1. Match every prediction to ground-truth labels at IoU ≥ 0.5 (per image).
  2. Each prediction becomes a (score, is_tp) pair → 85k of them.
  3. Treat is_tp as the binary target and the raw score ``p`` as the model's
     probability for "this box is a true defect". Convert to a logit
     ``z = log(p/(1-p))`` and fit a single scalar ``T`` (temperature) such
     that ``sigmoid(z / T)`` minimises NLL on (z, is_tp).
  4. Report a reliability diagram (10 bins) before and after.

Why temperature scaling
-----------------------
Modern detectors are usually *overconfident* — a "0.9" score means the model
is more sure than its accuracy warrants. T > 1 squashes scores toward 0.5
(makes the model less confident). T < 1 sharpens them. The single-scalar fit
is the simplest post-hoc calibration that works well in practice (Guo et al.
2017, "On Calibration of Modern Neural Networks").

This is post-hoc: we don't retrain the model. We just learn one number on a
held-out set and apply it at inference time.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from match import (
    CLASS_NAMES,
    Box,
    Prediction,
    match_predictions,
    parse_yolo_labels,
)


PREDS_PATH = Path("eval/test_predictions.json")
LABELS_DIR = Path("eval/test")
IMAGES_DIR_HINT = "(local images not required — sizes come from predictions JSON)"
OUTPUT_PATH = Path("eval/calibration.json")
IOU_THRESHOLD = 0.5
BIN_EDGES = np.linspace(0.0, 1.0, 11)  # 10 bins

# Strip the noise tail before fitting. Detectors emit thousands of near-zero
# predictions at conf=0.001 — they dominate NLL and bias a single-T fit toward
# noise instead of the operating range. 0.05 excludes ~92% of the noise while
# keeping everything above ~5% confidence, which is well below the demo
# threshold (0.3). This is standard practice for object-detection calibration.
CALIBRATION_FLOOR = 0.05


@dataclass(slots=True)
class CalibrationPoint:
    score: float
    is_tp: int  # 0 or 1


def collect_points() -> list[CalibrationPoint]:
    print(f"loading {PREDS_PATH}")
    images = json.loads(PREDS_PATH.read_text())
    print(f"  {len(images)} images, {sum(len(x['predictions']) for x in images)} predictions")

    points: list[CalibrationPoint] = []
    images_processed = 0
    for entry in images:
        name = entry["image"]
        w, h = entry["width"], entry["height"]

        stem = Path(name).stem
        labels = parse_yolo_labels(LABELS_DIR / f"{stem}.txt", w, h)
        preds = [
            Prediction(
                cls=p["class"], x1=p["bbox"][0], y1=p["bbox"][1],
                x2=p["bbox"][2], y2=p["bbox"][3], score=float(p["score"]),
            )
            for p in entry["predictions"]
        ]
        match_predictions(preds, labels, iou_threshold=IOU_THRESHOLD)
        for p in preds:
            points.append(CalibrationPoint(score=p.score, is_tp=1 if p.match == "tp" else 0))

        images_processed += 1
        if images_processed % 200 == 0:
            print(f"  matched {images_processed} images")

    return points


def reliability(points: list[CalibrationPoint], score_fn=lambda s: s) -> dict:
    """Bin predictions by score → (mean predicted score, observed fraction of TPs)."""
    rows = []
    ece = 0.0
    n_total = len(points)
    for i in range(len(BIN_EDGES) - 1):
        lo, hi = BIN_EDGES[i], BIN_EDGES[i + 1]
        in_bin = [pt for pt in points if lo <= score_fn(pt.score) < hi or (i == len(BIN_EDGES) - 2 and score_fn(pt.score) == hi)]
        if not in_bin:
            rows.append({"bin": [float(lo), float(hi)], "n": 0, "mean_score": None, "frac_tp": None})
            continue
        mean_score = float(np.mean([score_fn(pt.score) for pt in in_bin]))
        frac_tp = float(np.mean([pt.is_tp for pt in in_bin]))
        rows.append({"bin": [float(lo), float(hi)], "n": len(in_bin), "mean_score": mean_score, "frac_tp": frac_tp})
        ece += (len(in_bin) / n_total) * abs(mean_score - frac_tp)
    return {"bins": rows, "ece": float(ece)}


def fit_temperature(points: list[CalibrationPoint]) -> float:
    """L-BFGS over a single scalar T minimising NLL of sigmoid(logit / T)."""
    # Clamp scores away from 0 / 1 so logits are finite.
    EPS = 1e-6
    scores = torch.tensor(
        [max(EPS, min(1.0 - EPS, pt.score)) for pt in points],
        dtype=torch.float64,
    )
    targets = torch.tensor([float(pt.is_tp) for pt in points], dtype=torch.float64)
    logits = torch.log(scores / (1.0 - scores))

    log_T = torch.zeros(1, dtype=torch.float64, requires_grad=True)  # T = exp(log_T) > 0
    optim = torch.optim.LBFGS([log_T], lr=0.1, max_iter=100, line_search_fn="strong_wolfe")

    bce = torch.nn.BCEWithLogitsLoss(reduction="mean")

    def closure():
        optim.zero_grad()
        T = torch.exp(log_T)
        loss = bce(logits / T, targets)
        loss.backward()
        return loss

    optim.step(closure)
    T = float(torch.exp(log_T).item())
    return T


def apply_temperature(score: float, T: float) -> float:
    EPS = 1e-6
    s = max(EPS, min(1.0 - EPS, score))
    z = math.log(s / (1.0 - s))
    return 1.0 / (1.0 + math.exp(-z / T))


def main() -> None:
    points = collect_points()
    print(f"\ncollected {len(points)} (score, is_tp) pairs")
    print(f"  positive rate: {np.mean([pt.is_tp for pt in points]):.4f}")
    print(f"  mean raw score: {np.mean([pt.score for pt in points]):.4f}")

    print("\nreliability (raw scores)")
    rel_raw = reliability(points)
    for row in rel_raw["bins"]:
        if row["n"] == 0:
            continue
        gap = row["mean_score"] - row["frac_tp"]
        sign = "+" if gap > 0 else " "
        print(
            f"  [{row['bin'][0]:.1f}, {row['bin'][1]:.1f})  n={row['n']:>6}  "
            f"mean_score={row['mean_score']:.3f}  frac_tp={row['frac_tp']:.3f}  gap={sign}{gap:+.3f}"
        )
    print(f"  ECE (raw) = {rel_raw['ece']:.4f}")

    fit_points = [pt for pt in points if pt.score >= CALIBRATION_FLOOR]
    print(f"\nfitting temperature on {len(fit_points)} predictions with score >= {CALIBRATION_FLOOR}")
    T = fit_temperature(fit_points)
    print(f"  T = {T:.4f}")
    print("  T > 1 ⇒ model was overconfident (squash scores toward 0.5)")
    print("  T < 1 ⇒ model was underconfident (sharpen scores away from 0.5)")

    rel_cal = reliability(points, score_fn=lambda s: apply_temperature(s, T))
    print("\nreliability (after T)")
    for row in rel_cal["bins"]:
        if row["n"] == 0:
            continue
        gap = row["mean_score"] - row["frac_tp"]
        sign = "+" if gap > 0 else " "
        print(
            f"  [{row['bin'][0]:.1f}, {row['bin'][1]:.1f})  n={row['n']:>6}  "
            f"mean_score={row['mean_score']:.3f}  frac_tp={row['frac_tp']:.3f}  gap={sign}{gap:+.3f}"
        )
    print(f"  ECE (calibrated) = {rel_cal['ece']:.4f}")
    print(f"  ECE reduction: {rel_raw['ece']:.4f} → {rel_cal['ece']:.4f}  ({(1 - rel_cal['ece']/rel_raw['ece'])*100:.1f}% lower)")

    out = {
        "iou_threshold": IOU_THRESHOLD,
        "n_predictions": len(points),
        "positive_rate": float(np.mean([pt.is_tp for pt in points])),
        "mean_raw_score": float(np.mean([pt.score for pt in points])),
        "temperature": T,
        "reliability_raw": rel_raw,
        "reliability_calibrated": rel_cal,
    }
    OUTPUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
