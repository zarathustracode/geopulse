"""Dump per-prediction inference output for the full RDD2022 test split.

Writes /vol/rdd2022/runs/baseline/test_predictions.json:

    [
      {
        "image": "Japan_Japan_009963.jpg",
        "width": 600, "height": 600,
        "predictions": [
          {"bbox": [x1, y1, x2, y2], "class": "D00", "score": 0.77},
          ...
        ]
      },
      ...
    ]

Coordinates are in original image pixels (after ultralytics' letterbox + scale-back).
A low conf=0.001 is used on purpose: calibration needs the full score distribution,
not just the top of it.

Run:
    set -a; . ~/Development/Base/eidos/.env; set +a
    uv run --project ml modal run ml/training/dump_predictions.py
"""

import json

import modal

app = modal.App("geopulse-rdd2022-dump-predictions")

vol = modal.Volume.from_name("rdd2022", create_if_missing=False)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.11.0",
        "torchvision",
        "ultralytics>=8.3",
        "pillow>=10",
    )
)


@app.function(
    image=image,
    gpu="A10G",
    timeout=1 * 3600,
    volumes={"/vol": vol},
)
def dump():
    from pathlib import Path
    from PIL import Image as PILImage
    from ultralytics import YOLO

    weights = Path("/vol/rdd2022/runs/baseline/weights/best.pt")
    model = YOLO(str(weights))
    names = model.names  # {0: 'D00', ...}

    images_root = Path("/vol/rdd2022/images/test")
    images = sorted(images_root.glob("*.jpg")) + sorted(images_root.glob("*.JPG"))
    print(f"inference over {len(images)} test images at imgsz=640, conf=0.001")

    out: list[dict] = []
    BATCH = 32
    for i in range(0, len(images), BATCH):
        batch = images[i : i + BATCH]
        results = model.predict(
            source=[str(p) for p in batch],
            imgsz=640,
            conf=0.001,  # keep the low tail for calibration
            iou=0.6,
            device=0,
            verbose=False,
        )
        for path, r in zip(batch, results, strict=True):
            with PILImage.open(path) as im:
                w, h = im.size
            preds = []
            for box in r.boxes:
                cls = int(box.cls.item())
                score = float(box.conf.item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                preds.append({
                    "bbox": [x1, y1, x2, y2],
                    "class": names[cls],
                    "score": score,
                })
            out.append({
                "image": path.name,
                "width": w,
                "height": h,
                "predictions": preds,
            })
        if (i // BATCH) % 10 == 0:
            print(f"  {i + len(batch)} / {len(images)}")

    out_path = Path("/vol/rdd2022/runs/baseline/test_predictions.json")
    out_path.write_text(json.dumps(out))
    vol.commit()
    print(f"wrote {out_path}, {sum(len(x['predictions']) for x in out)} total predictions")


@app.local_entrypoint()
def main():
    dump.remote()
