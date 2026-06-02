"""One-shot helper: build a report.json with per-country clusters around Burgdorf.

Calls the existing YOLO detect path five times — once per country slice — using a
different (lat, lng) centre for each, so the map shows five visibly separate
clusters rather than a single dot. Each cluster sits within a few km of Burgdorf
so the demo's "Swiss mobile-mapping run" framing stays intact.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from geopulse_ml.detect import detect_yolo


WEIGHTS = Path("weights/best.pt")
SAMPLES_DIR = Path("samples_rdd")
OUTPUT = Path("report.json")
SCORE_THRESHOLD = 0.3
ACCEPT_ABOVE = 0.5
RADIUS_M = 250


# Country prefix in filename → display name, lat/lng centre near Burgdorf.
COUNTRIES = {
    "China_MotorBike": (47.0570, 7.6195),   # Burgdorf old town
    "Japan":           (47.0635, 7.6175),   # north-west
    "United_States":   (47.0660, 7.6320),   # north-east
    "Czech":           (47.0560, 7.6370),   # south-east
    "India":           (47.0500, 7.6230),   # south
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


def annotate(image_path: Path, detections, out_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for idx, det in enumerate(detections, start=1):
        x1, y1, x2, y2 = det.bbox
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        draw.text((x1, max(0, y1 - 22)), f"#{idx} {det.label} {det.score:.2f}", fill="red", font=font)
    image.save(out_path)


def main() -> None:
    rng = random.Random(0xC0DE)
    records: list[dict] = []
    next_id = 1

    images = sorted(SAMPLES_DIR.glob("*.jpg"))
    images = [p for p in images if not p.stem.endswith("_annotated")]

    for image in images:
        country = country_of(image.name)
        if country is None:
            continue
        lat0, lng0 = COUNTRIES[country]

        detections = detect_yolo(image, WEIGHTS, score_threshold=SCORE_THRESHOLD)
        if not detections:
            print(f"  {image.name}: no detections")
            continue
        annotate(image, detections, image.with_name(f"{image.stem}_annotated.jpg"))

        for det in detections:
            lat, lng = disc_point(rng, lat0, lng0, RADIUS_M)
            status = "accepted" if det.score >= ACCEPT_ABOVE else "needs_review"
            records.append(asdict(det) | {
                "id": next_id,
                "status": status,
                "latitude": lat,
                "longitude": lng,
                "source_image": f"samples_rdd/{image.name}",
            })
            next_id += 1
        print(f"  {image.name} ({country}): {len(detections)} detection(s)")

    report = {
        "model": "ultralytics.yolo11m.rdd2022_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score_threshold": SCORE_THRESHOLD,
        "kept_classes": ["D00", "D10", "D20", "D40"],
        "detections": records,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {len(records)} detections to {OUTPUT}")


if __name__ == "__main__":
    main()
