"""Build report.json with per-marker TP / FP / FN ground-truth labels.

For each of the 15 RDD2022 demo images:

  - run YOLO inference at the demo threshold (conf ≥ 0.3),
  - match the predictions to ground-truth labels at IoU ≥ 0.5 (greedy by score),
  - emit one marker per surviving prediction (tagged ``tp`` or ``fp``),
  - emit one marker per unmatched label (``fn``, no image — the model missed it).

Each country slice gets its own (lat, lng) centre near Burgdorf so the map
shows five visibly separate clusters and the cross-country gap is geographic.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from eval.match import (
    Box,
    Prediction,
    match_predictions,
    parse_yolo_labels,
)
from geopulse_ml.detect import detect_yolo


WEIGHTS = Path("weights/best.pt")
SAMPLES_DIR = Path("samples_rdd")
LABELS_DIR = Path("eval/test")
CALIBRATION_PATH = Path("eval/calibration.json")
OUTPUT = Path("report.json")
SCORE_THRESHOLD = 0.3
ACCEPT_ABOVE = 0.5
IOU_THRESHOLD = 0.5
RADIUS_M = 250


def _load_temperature(path: Path) -> float:
    if not path.exists():
        return 1.0
    return float(json.loads(path.read_text())["temperature"])


def _temperature_apply(score: float, T: float) -> float:
    EPS = 1e-6
    s = max(EPS, min(1.0 - EPS, score))
    z = math.log(s / (1.0 - s))
    return 1.0 / (1.0 + math.exp(-z / T))


COUNTRIES = {
    "China_MotorBike": (47.0570, 7.6195),
    "Japan":           (47.0635, 7.6175),
    "United_States":   (47.0660, 7.6320),
    "Czech":           (47.0560, 7.6370),
    "India":           (47.0500, 7.6230),
}


def country_of(filename: str) -> str | None:
    for prefix in COUNTRIES:
        if filename.startswith(prefix):
            return prefix
    return None


def disc_point(rng: random.Random, lat: float, lng: float, radius_m: float):
    r = math.sqrt(rng.random()) * radius_m
    theta = rng.random() * 2 * math.pi
    dlat = (r * math.sin(theta)) / 111_000
    dlng = (r * math.cos(theta)) / (111_000 * math.cos(math.radians(lat)))
    return lat + dlat, lng + dlng


def annotate(image_path: Path, predictions: list[Prediction], labels: list[Box], out_path: Path) -> None:
    """Draw: TP green, FP red, FN dashed grey (label only — model didn't propose it)."""
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    matched_label_indices = {p.matched_label_idx for p in predictions if p.match == "tp"}

    for pred in predictions:
        color = "#10b981" if pred.match == "tp" else "#e11d48"
        draw.rectangle((pred.x1, pred.y1, pred.x2, pred.y2), outline=color, width=3)
        tag = "TP" if pred.match == "tp" else "FP"
        draw.text(
            (pred.x1, max(0, pred.y1 - 20)),
            f"{tag} {pred.cls} {pred.score:.2f}",
            fill=color,
            font=font,
        )

    for i, lbl in enumerate(labels):
        if i in matched_label_indices:
            continue
        # FN — model missed it. Dashed grey would be ideal; PIL doesn't do dashes
        # natively, so a thinner grey outline gets the point across.
        draw.rectangle((lbl.x1, lbl.y1, lbl.x2, lbl.y2), outline="#64748b", width=2)
        draw.text(
            (lbl.x1, max(0, lbl.y1 - 20)),
            f"FN {lbl.cls} (missed)",
            fill="#64748b",
            font=font,
        )

    image.save(out_path)


def main() -> None:
    rng = random.Random(0xC0DE)
    records: list[dict] = []
    next_id = 1
    T = _load_temperature(CALIBRATION_PATH)
    print(f"  using temperature T = {T:.4f} from {CALIBRATION_PATH}")

    images = sorted(SAMPLES_DIR.glob("*.jpg"))
    images = [p for p in images if not p.stem.endswith("_annotated")]

    tp_total = fp_total = fn_total = 0

    for image in images:
        country = country_of(image.name)
        if country is None:
            continue
        lat0, lng0 = COUNTRIES[country]

        raw = detect_yolo(image, WEIGHTS, score_threshold=SCORE_THRESHOLD)
        preds = [
            Prediction(cls=d.label, x1=d.bbox[0], y1=d.bbox[1], x2=d.bbox[2], y2=d.bbox[3], score=d.score)
            for d in raw
        ]

        with Image.open(image) as im:
            w, h = im.size
        labels = parse_yolo_labels(LABELS_DIR / f"{image.stem}.txt", w, h)

        result = match_predictions(preds, labels, iou_threshold=IOU_THRESHOLD)
        tp_total += result.tp_count
        fp_total += result.fp_count
        fn_total += result.fn_count

        annotate(image, preds, labels, image.with_name(f"{image.stem}_annotated.jpg"))
        rel_image = f"samples_rdd/{image.name}"

        for pred in preds:
            lat, lng = disc_point(rng, lat0, lng0, RADIUS_M)
            status = "accepted" if pred.score >= ACCEPT_ABOVE else "needs_review"
            records.append({
                "label": pred.cls,
                "score": pred.score,
                "calibrated_score": _temperature_apply(pred.score, T),
                "bbox": [pred.x1, pred.y1, pred.x2, pred.y2],
                "id": next_id,
                "status": status,
                "latitude": lat,
                "longitude": lng,
                "source_image": rel_image,
                "match_status": pred.match,  # "tp" | "fp"
            })
            next_id += 1

        for fn in result.false_negatives:
            lat, lng = disc_point(rng, lat0, lng0, RADIUS_M)
            records.append({
                "label": fn.cls,
                "score": 0.0,  # the model didn't propose this — no score
                "bbox": [fn.x1, fn.y1, fn.x2, fn.y2],
                "id": next_id,
                "status": "needs_review",
                "latitude": lat,
                "longitude": lng,
                "source_image": rel_image,
                "match_status": "fn",
            })
            next_id += 1

        print(
            f"  {image.name} ({country}): "
            f"TP {result.tp_count}  FP {result.fp_count}  FN {result.fn_count}"
        )

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    print()
    print(f"  totals: TP {tp_total}  FP {fp_total}  FN {fn_total}")
    print(f"  precision @ conf≥{SCORE_THRESHOLD} = {precision:.3f}")
    print(f"  recall    @ conf≥{SCORE_THRESHOLD} = {recall:.3f}")

    report = {
        "model": "ultralytics.yolo11m.rdd2022_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score_threshold": SCORE_THRESHOLD,
        "iou_threshold": IOU_THRESHOLD,
        "temperature": T,
        "kept_classes": ["D00", "D10", "D20", "D40"],
        "demo_image_metrics": {
            "tp": tp_total,
            "fp": fp_total,
            "fn": fn_total,
            "precision": precision,
            "recall": recall,
        },
        "detections": records,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {len(records)} markers to {OUTPUT}")


if __name__ == "__main__":
    main()
