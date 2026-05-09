"""Fine-tune YOLO11m on RDD2022 (Modal A10G).

Reads dataset from Modal volume `rdd2022` (populated by download_rdd2022.py).
Writes weights to /vol/rdd2022/runs/baseline/weights/best.pt and the
training log to /vol/rdd2022/runs/baseline/results.csv.

Run:
    set -a; . ~/Development/Base/eidos/.env; set +a
    export PYTHONIOENCODING=utf-8
    uv run --project ml modal run ml/training/train_modal.py
"""

import modal

app = modal.App("geopulse-rdd2022-train")

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


@app.function(
    image=image,
    gpu="A10G",
    timeout=6 * 3600,  # 6 hours; 30 epochs on A10G should fit comfortably
    volumes={"/vol": vol},
)
def train():
    import shutil
    from pathlib import Path
    from ultralytics import YOLO

    yaml_path = Path("/vol/rdd2022/rdd2022.yaml")
    if not yaml_path.exists():
        raise RuntimeError(
            f"{yaml_path} missing. Run download_rdd2022.py first."
        )
    print(f"using dataset config: {yaml_path}")
    print(yaml_path.read_text())

    runs_root = Path("/vol/rdd2022/runs")
    runs_root.mkdir(parents=True, exist_ok=True)

    model = YOLO("yolo11m.pt")  # COCO-pretrained backbone
    results = model.train(
        data=str(yaml_path),
        epochs=30,
        batch=32,
        imgsz=640,
        patience=10,
        device=0,
        project=str(runs_root),
        name="baseline",
        exist_ok=True,
        verbose=True,
        # ultralytics defaults for everything else
    )

    # Surface the best.pt path so the caller can find it.
    best_pt = runs_root / "baseline" / "weights" / "best.pt"
    if not best_pt.exists():
        # Fallback to last.pt if early stop produced no improvement
        last_pt = runs_root / "baseline" / "weights" / "last.pt"
        if last_pt.exists():
            shutil.copy(last_pt, best_pt)
    print(f"\ntrained weights at {best_pt}")
    vol.commit()

    return {
        "best_pt": str(best_pt),
        "exists": best_pt.exists(),
        "size_mb": round(best_pt.stat().st_size / 1e6, 1) if best_pt.exists() else None,
    }


@app.local_entrypoint()
def main():
    out = train.remote()
    print("\n=== Training complete ===")
    print(out)
