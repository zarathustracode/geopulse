# GeoPulse Fine-Tuning — Day 1–2 Spec

**Goal:** RDD2022 downloaded + a fine-tuned YOLO11m baseline + honest evaluation, all running on Modal. End of Day 2 we can quote a defensible mAP number on a real public benchmark.

**Time budget:** 2 days, ~10 hours of focused work. Most of the time is data-conversion and waiting for training; the code itself is small.

**Compute budget:** ~$10 of Modal credits (one A10G training run ≈ 5 hours @ $1.10/hr).

---

## Non-goals (DO NOT DO IN DAY 1-2)

❌ Don't add the VLM hybrid (Day 6–7)
❌ Don't do calibration / temperature scaling (Day 8–9)
❌ Don't build the active-learning loop (Day 10)
❌ Don't touch GeoPulse `backend/` or `frontend/` (Day 11–12)
❌ Don't tune hyperparameters beyond ultralytics defaults
❌ Don't try multiple architectures — YOLO11m only for the baseline

The point is: **a trustworthy first number**. Polish comes later.

---

## Deliverables

### 1. Repository layout

Add under `GeoPulse/ml/`:

```
ml/
├─ training/
│  ├─ __init__.py
│  ├─ download_rdd2022.py     # one-shot: pull dataset, convert to YOLO format, upload to Modal volume
│  ├─ train_modal.py          # Modal app: fine-tune YOLO11m on RDD2022
│  ├─ eval_modal.py           # Modal app: load weights + compute mAP, per-class, per-country
│  └─ rdd2022.yaml            # YOLO dataset config (paths + class names)
└─ ... (existing inference CLI untouched)
```

The training package is `ml/training/` rather than under `src/geopulse_ml/` — training is offline tooling, not part of the deployable inference package.

### 2. Dataset

**RDD2022 source:** `https://github.com/sekilab/RoadDamageDetector` — original repository with download links to per-country zips on Google Drive. Six countries: Japan, India, Czech, Norway, US, China. Total size ~5 GB, ~47K labeled images.

**Conversion:** RDD2022 ships in Pascal VOC format (XML annotations). Need to convert to YOLO format:
- Each image gets a `.txt` with one row per box: `class_id cx cy w h` (all normalized to [0, 1])
- Class names: `D00` (longitudinal crack), `D10` (transverse crack), `D20` (alligator crack), `D40` (pothole). RDD2022 has more sub-types but the four canonical classes are the safe baseline.
- Train/val/test split: 80/10/10, stratified by country to keep per-country evaluation possible.

**Data target:** Modal persistent volume named `rdd2022`, structured as:
```
rdd2022/
├─ images/
│  ├─ train/
│  ├─ val/
│  └─ test/
└─ labels/
   ├─ train/
   ├─ val/
   └─ test/
```

`rdd2022.yaml`:
```yaml
path: /vol/rdd2022
train: images/train
val: images/val
test: images/test
nc: 4
names: [D00, D10, D20, D40]
```

### 3. Training run

`train_modal.py` Modal app:

- **Image:** Debian slim Python 3.11 + `torch==2.11.0` + `ultralytics>=8.3` + `numpy`. Mount `rdd2022` volume.
- **Hardware:** A10G GPU (24 GB), single-GPU.
- **Hyperparameters:** ultralytics defaults except:
  - Pretrained backbone: `yolo11m.pt` (COCO weights)
  - epochs: 30
  - batch: 32
  - imgsz: 640
  - patience: 10 (early-stop on val mAP@0.5:0.95)
- **Output:** weights to `/vol/rdd2022/runs/baseline/weights/best.pt` + training log.

Acceptance: `modal run train_modal.py` returns a `best.pt` saved to the volume + a JSON log of per-epoch val metrics.

### 4. Evaluation

`eval_modal.py` Modal app:

- Loads `best.pt`, runs on `images/test`, computes:
  - **mAP@0.5** and **mAP@0.5:0.95** (overall)
  - **Per-class mAP@0.5:0.95** (4 classes)
  - **Per-country mAP@0.5** (group test images by country prefix in filename)
  - **Inference latency**: median + p95 ms per image at batch=1, A10G
- Saves `eval_report.json` to volume with all numbers.
- Prints a clean table at the end.

This is the single source of truth for "what's our baseline number." Don't ad-hoc anything else for Day 1–2.

---

## Acceptance criteria

✅ RDD2022 downloaded, converted, uploaded to Modal volume `rdd2022` (one-time, ~30 min on a fast connection).
✅ `train_modal.py` runs end-to-end on Modal A10G; weights saved to volume.
✅ `eval_modal.py` runs end-to-end; produces `eval_report.json` with all required metrics.
✅ Final printed table includes:
  - mAP@0.5 overall (target: ≥ 0.55, the typical YOLO baseline range)
  - mAP@0.5:0.95 overall (target: ≥ 0.30)
  - Per-class mAP@0.5:0.95 (4 numbers)
  - Per-country mAP@0.5 (6 numbers)
  - Median inference latency (target: ≤ 30 ms on A10G at batch=1)
✅ A short markdown summary at `ml/training/DAY_1_2_RESULTS.md` with the table + 1 paragraph honest interpretation.

If mAP@0.5:0.95 is below 0.30, **stop and diagnose** before adding any complexity. Likely causes: bad train/val split, label conversion bug, or stratified-by-country shuffle gone wrong.

---

## Out-of-scope clarifications

**Q: Should I download all six countries or just one?**
A: All six. The cross-country eval is part of the story.

**Q: Should I use YOLO11s for faster iteration?**
A: No. YOLO11m is the baseline. We can compare to s/l later if needed.

**Q: Should I try mosaic augmentation / mixup / etc.?**
A: No, ultralytics defaults only. Hyperparameter tuning is Day 14 territory if at all.

**Q: Should I integrate this into GeoPulse `ml/`?**
A: No, that's Day 11–12. Day 1–2 is purely "do the training, get the number."

**Q: What if RDD2022 download is slow / Google Drive throttles?**
A: There's a HuggingFace mirror at `Multimedia-Eurecat/RDD2022` — same content, faster. Or the ultralytics ecosystem has automated downloaders for common datasets.

**Q: What if the YOLO ultralytics package conflicts with our other Python deps?**
A: The training environment is its own Modal image. It has nothing to do with the Eidos Python env. Conflicts can't happen.

---

## Modal pattern (reuse from linear-attention work)

```python
import modal

app = modal.App("geopulse-rdd2022-train")

vol = modal.Volume.from_name("rdd2022", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.11.0", "ultralytics>=8.3", "numpy>=1.26")
)


@app.function(
    image=image,
    gpu="A10G",
    timeout=6 * 3600,  # 6 hours
    volumes={"/vol": vol},
)
def train():
    from ultralytics import YOLO
    model = YOLO("yolo11m.pt")
    model.train(
        data="/vol/rdd2022/rdd2022.yaml",
        epochs=30,
        batch=32,
        imgsz=640,
        patience=10,
        device=0,
        project="/vol/rdd2022/runs",
        name="baseline",
        exist_ok=True,
    )


@app.local_entrypoint()
def main():
    train.remote()
```

Same shape as today's `phase4_*.py` runners. Volume replaces `add_local_dir` because the dataset is too big to mount and we want it persistent across runs.

---

## Definition of done

After Day 2, we have:
- A Modal-trained YOLO11m on RDD2022 with defensible numbers
- A Modal volume with weights + dataset that subsequent days can build on
- A one-paragraph honest writeup of where we land vs. published baselines

That's enough to move to Day 3 (deeper eval — calibration, per-domain breakdown, road-segment-level recall) without reworking infrastructure.

---

## What I'll do vs. what you'll do

I'll write:
- `download_rdd2022.py` (Pascal VOC → YOLO conversion script)
- `train_modal.py` (Modal training app)
- `eval_modal.py` (Modal evaluation app)
- `rdd2022.yaml` (dataset config)
- `DAY_1_2_RESULTS.md` (after eval lands)

You'll need to:
- Have Modal credits (already done, $30/mo)
- Run the download script locally to a Modal volume (one-time, ~30 min)
- Approve the training run when ready
- Look at the numbers and decide if Day 3+ proceeds as planned

Estimated total wallclock from "go" to "have the numbers": ~6 hours of which ~4 are GPU time on Modal that runs in the background.
