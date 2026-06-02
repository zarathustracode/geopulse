"""CLI: image → detections → human review → JSON report.

This mirrors the shape of digital survey's Infrastruktur-Inventarisierung
workflow: a model proposes, a human confirms, the result is a reviewable
record. Confidence scores out of Mask R-CNN are NOT calibrated — treating the
0.5 threshold as meaningful is a modelling choice, not a statement about
ground truth.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .detect import Detection, detect, detect_yolo

app = typer.Typer(help="Human-in-the-loop review for street-imagery detections.")
console = Console()

DEFAULT_KEEP = frozenset({"stop sign", "traffic light", "fire hydrant"})
# Burgdorf, Switzerland — digital survey's home town. The demo pretends the
# image was captured on a mobile-mapping run around here.
DEFAULT_CENTER_LAT = 47.0609
DEFAULT_CENTER_LNG = 7.6250
DEFAULT_RADIUS_M = 300


def _disc_point(
    rng: random.Random, center_lat: float, center_lng: float, radius_m: float
) -> tuple[float, float]:
    """Uniform sample inside a disc of radius_m around (center_lat, center_lng).

    Stand-in for a real bbox→world projection: a production pipeline would use
    camera intrinsics + pose from GNSS/IMU to put each detection on the ground
    plane. Here we just scatter within a radius so the reviewer UI has
    something plausible to render.
    """
    r = math.sqrt(rng.random()) * radius_m
    theta = rng.random() * 2 * math.pi
    # Flat-earth approximation — fine at city scale, wrong at country scale.
    dlat = (r * math.sin(theta)) / 111_000
    dlng = (r * math.cos(theta)) / (111_000 * math.cos(math.radians(center_lat)))
    return center_lat + dlat, center_lng + dlng


def _annotate(image_path: Path, detections: list[Detection], out_path: Path) -> None:
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


@app.command()
def review(
    image: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Street-imagery input.")],
    output: Annotated[Path, typer.Option(help="Where to write the JSON report.")] = Path("report.json"),
    annotated: Annotated[Path, typer.Option(help="Where to write the annotated preview image.")] = Path("annotated.jpg"),
    score_threshold: Annotated[float, typer.Option(min=0.0, max=1.0)] = 0.5,
    classes: Annotated[list[str] | None, typer.Option(help="COCO class names to keep. Omit for a sensible default.")] = None,
    center_lat: Annotated[float, typer.Option(help="Latitude for the pretend survey-run centre.")] = DEFAULT_CENTER_LAT,
    center_lng: Annotated[float, typer.Option(help="Longitude for the pretend survey-run centre.")] = DEFAULT_CENTER_LNG,
    radius_m: Annotated[float, typer.Option(help="Disc radius (m) to scatter detections within.")] = DEFAULT_RADIUS_M,
) -> None:
    keep = frozenset(classes) if classes else DEFAULT_KEEP

    console.print(Panel.fit(f"[bold]Loading model[/] (first run downloads ~170 MB of COCO weights)"))
    detections = detect(image, score_threshold=score_threshold, keep_classes=keep)

    if not detections:
        console.print("[yellow]No detections above threshold. Try lowering --score-threshold or widening --classes.[/]")
        raise typer.Exit(code=0)

    _annotate(image, detections, annotated)
    console.print(f"Annotated preview: [cyan]{annotated}[/]")

    table = Table(title=f"{len(detections)} proposals", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("class")
    table.add_column("score", justify="right")
    table.add_column("bbox (x1,y1,x2,y2)")
    for idx, det in enumerate(detections, start=1):
        bbox = ", ".join(f"{v:.0f}" for v in det.bbox)
        table.add_row(str(idx), det.label, f"{det.score:.3f}", bbox)
    console.print(table)

    rng = random.Random(hash(image.resolve().as_posix()) & 0xFFFFFFFF)

    records = []
    for idx, det in enumerate(detections, start=1):
        answer = Prompt.ask(
            f"[bold]#{idx}[/] {det.label} (score {det.score:.2f}) — accept?",
            choices=["y", "n", "s"],
            default="y",
        )
        status = {"y": "accepted", "n": "rejected", "s": "needs_review"}[answer]
        record = asdict(det) | {"status": status, "id": idx}
        if status != "rejected":
            lat, lng = _disc_point(rng, center_lat, center_lng, radius_m)
            record |= {"latitude": lat, "longitude": lng}
        records.append(record)

    report = {
        "source_image": str(image.resolve()),
        "model": "torchvision.maskrcnn_resnet50_fpn.COCO_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "survey_run": {
            "center_lat": center_lat,
            "center_lng": center_lng,
            "radius_m": radius_m,
        },
        "score_threshold": score_threshold,
        "kept_classes": sorted(keep),
        "detections": records,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    counts = {s: sum(1 for r in records if r["status"] == s) for s in ("accepted", "rejected", "needs_review")}
    console.print(
        f"[green]{counts['accepted']} accepted[/] · "
        f"[red]{counts['rejected']} rejected[/] · "
        f"[yellow]{counts['needs_review']} flagged[/] → {output}"
    )


@app.command()
def batch(
    images: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, help="Street-imagery inputs.")],
    output: Annotated[Path, typer.Option(help="Where to write the merged JSON report.")] = Path("report.json"),
    score_threshold: Annotated[float, typer.Option(min=0.0, max=1.0)] = 0.5,
    classes: Annotated[list[str] | None, typer.Option(help="COCO class names to keep.")] = None,
    center_lat: Annotated[float, typer.Option()] = DEFAULT_CENTER_LAT,
    center_lng: Annotated[float, typer.Option()] = DEFAULT_CENTER_LNG,
    radius_m: Annotated[float, typer.Option()] = DEFAULT_RADIUS_M,
    base_dir: Annotated[Path, typer.Option(help="Directory that source_image paths are written relative to.")] = Path.cwd(),
    accept_above: Annotated[float, typer.Option(min=0.0, max=1.0, help="Scores at or above are auto-accepted; below are flagged needs_review.")] = 0.75,
) -> None:
    """Non-interactive: run the detector on multiple images and merge into one report."""
    keep = frozenset(classes) if classes else DEFAULT_KEEP
    console.print(Panel.fit(f"[bold]Loading model[/] on {len(images)} image(s) (first run downloads ~170 MB)"))

    rng = random.Random(0xC0DE)
    records: list[dict] = []
    next_id = 1
    base = base_dir.resolve()

    for image in images:
        detections = detect(image, score_threshold=score_threshold, keep_classes=keep)
        if not detections:
            console.print(f"[dim]{image.name}: no detections above threshold[/]")
            continue
        annotated_path = image.with_name(f"{image.stem}_annotated.jpg")
        _annotate(image, detections, annotated_path)
        try:
            rel = image.resolve().relative_to(base).as_posix()
        except ValueError:
            rel = image.name
        for det in detections:
            lat, lng = _disc_point(rng, center_lat, center_lng, radius_m)
            status = "accepted" if det.score >= accept_above else "needs_review"
            records.append(asdict(det) | {
                "id": next_id,
                "status": status,
                "latitude": lat,
                "longitude": lng,
                "source_image": rel,
            })
            next_id += 1
        console.print(f"[green]{image.name}[/]: {len(detections)} detection(s)")

    report = {
        "model": "torchvision.maskrcnn_resnet50_fpn.COCO_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "survey_run": {
            "center_lat": center_lat,
            "center_lng": center_lng,
            "radius_m": radius_m,
        },
        "score_threshold": score_threshold,
        "kept_classes": sorted(keep),
        "detections": records,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    counts = {s: sum(1 for r in records if r["status"] == s) for s in ("accepted", "needs_review")}
    console.print(
        f"[green]{counts['accepted']} accepted[/] - "
        f"[yellow]{counts['needs_review']} flagged[/] -> {output}"
    )


@app.command()
def yolo(
    images: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, help="Street-imagery inputs.")],
    weights: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Path to YOLO best.pt.")] = Path("weights/best.pt"),
    output: Annotated[Path, typer.Option(help="Where to write the merged JSON report.")] = Path("report.json"),
    score_threshold: Annotated[float, typer.Option(min=0.0, max=1.0)] = 0.3,
    center_lat: Annotated[float, typer.Option()] = DEFAULT_CENTER_LAT,
    center_lng: Annotated[float, typer.Option()] = DEFAULT_CENTER_LNG,
    radius_m: Annotated[float, typer.Option()] = DEFAULT_RADIUS_M,
    base_dir: Annotated[Path, typer.Option(help="Directory that source_image paths are written relative to.")] = Path.cwd(),
    accept_above: Annotated[float, typer.Option(min=0.0, max=1.0)] = 0.5,
) -> None:
    """RDD2022 YOLO inference: cracks (D00/D10/D20) and potholes (D40) over real road photos."""
    console.print(Panel.fit(f"[bold]Loading RDD2022 YOLO[/] ({weights}) on {len(images)} image(s)"))

    rng = random.Random(0xC0DE)
    records: list[dict] = []
    next_id = 1
    base = base_dir.resolve()

    for image in images:
        detections = detect_yolo(image, weights, score_threshold=score_threshold)
        if not detections:
            console.print(f"[dim]{image.name}: no detections above threshold[/]")
            continue
        annotated_path = image.with_name(f"{image.stem}_annotated.jpg")
        _annotate(image, detections, annotated_path)
        try:
            rel = image.resolve().relative_to(base).as_posix()
        except ValueError:
            rel = image.name
        for det in detections:
            lat, lng = _disc_point(rng, center_lat, center_lng, radius_m)
            status = "accepted" if det.score >= accept_above else "needs_review"
            records.append(asdict(det) | {
                "id": next_id,
                "status": status,
                "latitude": lat,
                "longitude": lng,
                "source_image": rel,
            })
            next_id += 1
        console.print(f"[green]{image.name}[/]: {len(detections)} detection(s)")

    report = {
        "model": "ultralytics.yolo11m.rdd2022_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "survey_run": {
            "center_lat": center_lat,
            "center_lng": center_lng,
            "radius_m": radius_m,
        },
        "score_threshold": score_threshold,
        "kept_classes": ["D00", "D10", "D20", "D40"],
        "detections": records,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    counts = {s: sum(1 for r in records if r["status"] == s) for s in ("accepted", "needs_review")}
    console.print(
        f"[green]{counts['accepted']} accepted[/] - "
        f"[yellow]{counts['needs_review']} flagged[/] -> {output}"
    )


if __name__ == "__main__":
    app()
