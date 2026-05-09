"""Evaluate the fine-tuned YOLO11m on RDD2022 test split (Modal A10G).

Reports:
  - mAP@0.5, mAP@0.5:0.95 overall
  - Per-class mAP@0.5:0.95 (D00, D10, D20, D40)
  - Per-country mAP@0.5 (groups by filename prefix)
  - Inference latency: median + p95 ms per image at batch=1

Writes /vol/rdd2022/runs/baseline/eval_report.json with all numbers and
prints a clean table.

Run:
    set -a; . ~/Development/Base/eidos/.env; set +a
    export PYTHONIOENCODING=utf-8
    uv run --project ml modal run ml/training/eval_modal.py
"""

import json
import modal

app = modal.App("geopulse-rdd2022-eval")

vol = modal.Volume.from_name("rdd2022", create_if_missing=False)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")  # ultralytics -> opencv needs libGL
    .pip_install(
        "torch==2.11.0",
        "torchvision",
        "ultralytics>=8.3",
        "numpy>=1.26",
        "pillow>=10",
    )
)


def _country_from_filename(name: str) -> str:
    # Filenames are written as "{country}_{stem}.jpg" by the downloader.
    if "_" not in name:
        return "unknown"
    return name.split("_", 1)[0]


@app.function(
    image=image,
    gpu="A10G",
    timeout=2 * 3600,
    volumes={"/vol": vol},
)
def evaluate():
    import time
    from collections import defaultdict
    from pathlib import Path
    import torch
    from PIL import Image
    from ultralytics import YOLO

    weights = Path("/vol/rdd2022/runs/baseline/weights/best.pt")
    if not weights.exists():
        raise RuntimeError(f"{weights} missing. Run train_modal.py first.")
    print(f"loading weights: {weights}")
    model = YOLO(str(weights))

    yaml_path = Path("/vol/rdd2022/rdd2022.yaml")

    # ----- 1. Overall + per-class mAP via ultralytics .val() -----
    print("\n=== overall + per-class metrics ===")
    metrics = model.val(
        data=str(yaml_path),
        split="test",
        imgsz=640,
        batch=32,
        device=0,
        verbose=True,
    )
    map_5095 = float(metrics.box.map)        # mAP@0.5:0.95
    map_50 = float(metrics.box.map50)        # mAP@0.5
    per_class_5095 = [float(x) for x in metrics.box.maps]  # per class
    class_names = list(model.names.values())

    # ----- 2. Per-country mAP@0.5 -----
    # Run a separate eval per country: filter test images by country prefix.
    print("\n=== per-country mAP@0.5 ===")
    test_images_root = Path("/vol/rdd2022/images/test")
    test_images = sorted(test_images_root.glob("*.jpg")) + sorted(test_images_root.glob("*.JPG"))

    country_groups = defaultdict(list)
    for img in test_images:
        country_groups[_country_from_filename(img.name)].append(img)
    print(f"  countries in test split: {dict((c, len(v)) for c, v in country_groups.items())}")

    per_country_map50 = {}
    for country, imgs in country_groups.items():
        if len(imgs) < 5:
            print(f"  skipping {country}: only {len(imgs)} test images")
            continue
        # Use a temp YAML pointing only at this country's images.
        tmp_dir = Path(f"/tmp/country_{country}")
        (tmp_dir / "images" / "test").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "labels" / "test").mkdir(parents=True, exist_ok=True)
        # symlinks to avoid copying
        for img in imgs:
            link = tmp_dir / "images" / "test" / img.name
            if not link.exists():
                link.symlink_to(img)
            lbl_src = Path("/vol/rdd2022/labels/test") / (img.stem + ".txt")
            if lbl_src.exists():
                lbl_link = tmp_dir / "labels" / "test" / (img.stem + ".txt")
                if not lbl_link.exists():
                    lbl_link.symlink_to(lbl_src)
        tmp_yaml = tmp_dir / f"{country}.yaml"
        tmp_yaml.write_text(
            f"path: {tmp_dir}\n"
            f"train: images/test\n"  # ultralytics requires train field; reuse test
            f"val: images/test\n"
            f"test: images/test\n"
            f"nc: 4\n"
            f"names: [D00, D10, D20, D40]\n"
        )
        country_metrics = model.val(
            data=str(tmp_yaml),
            split="test",
            imgsz=640,
            batch=32,
            device=0,
            verbose=False,
        )
        per_country_map50[country] = float(country_metrics.box.map50)
        print(f"  {country:<20} mAP@0.5 = {per_country_map50[country]:.4f}  (n={len(imgs)})")

    # ----- 3. Inference latency at batch=1 -----
    print("\n=== inference latency (batch=1) ===")
    latency_ms = []
    sample = test_images[: min(50, len(test_images))]
    # Warm up
    for img in sample[:5]:
        _ = model.predict(source=str(img), imgsz=640, device=0, verbose=False)
    for img in sample:
        torch.cuda.synchronize()
        t0 = time.time()
        _ = model.predict(source=str(img), imgsz=640, device=0, verbose=False)
        torch.cuda.synchronize()
        latency_ms.append((time.time() - t0) * 1000)
    latency_ms.sort()
    p50 = latency_ms[len(latency_ms) // 2]
    p95 = latency_ms[int(len(latency_ms) * 0.95)]
    print(f"  median  {p50:.1f} ms")
    print(f"  p95     {p95:.1f} ms")

    report = {
        "overall": {
            "mAP_50": map_50,
            "mAP_50_95": map_5095,
        },
        "per_class_mAP_50_95": dict(zip(class_names, per_class_5095)),
        "per_country_mAP_50": per_country_map50,
        "latency_ms": {
            "median": p50,
            "p95": p95,
            "n_samples": len(latency_ms),
        },
        "n_test_images": len(test_images),
    }

    out_path = Path("/vol/rdd2022/runs/baseline/eval_report.json")
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {out_path}")
    vol.commit()
    return report


@app.local_entrypoint()
def main():
    report = evaluate.remote()
    print("\n=== EVALUATION REPORT ===")
    print(f"mAP@0.5      : {report['overall']['mAP_50']:.4f}")
    print(f"mAP@0.5:0.95 : {report['overall']['mAP_50_95']:.4f}")
    print()
    print("Per class (mAP@0.5:0.95):")
    for c, v in report["per_class_mAP_50_95"].items():
        print(f"  {c:<6} {v:.4f}")
    print()
    print("Per country (mAP@0.5):")
    for c, v in report["per_country_mAP_50"].items():
        print(f"  {c:<20} {v:.4f}")
    print()
    print(f"Latency (batch=1, A10G): median {report['latency_ms']['median']:.1f} ms, "
          f"p95 {report['latency_ms']['p95']:.1f} ms")
    print(f"Test set size: {report['n_test_images']}")
