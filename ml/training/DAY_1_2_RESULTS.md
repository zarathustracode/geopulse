# Day 1-2 Results — RDD2022 YOLO11m Baseline

Date: 2026-05-09 → 2026-05-10
Modal app: `geopulse-rdd2022-train` + `geopulse-rdd2022-eval`
Total compute spend: ~$6 of Modal credits (download $0.10, training ~$5.5 / 4h on A10G, eval $0.30)

## Headline numbers

| Metric | Target (spec) | Actual |
|---|---|---|
| mAP@0.5 overall | ≥ 0.55 | **0.636** ✓ |
| mAP@0.5:0.95 overall | ≥ 0.30 | **0.324** ✓ |
| Latency (A10G, batch=1) | ≤ 30 ms | **11.3 ms (median), 12.3 ms (p95)** ✓ |

Day 1-2 spec acceptance hit cleanly. No hyperparameter tuning, no augmentation beyond ultralytics defaults.

## Per-class breakdown (mAP@0.5 / mAP@0.5:0.95)

| Class | Description | mAP@0.5 | mAP@0.5:0.95 | Test instances |
|---|---|---:|---:|---:|
| **All** | overall | **0.636** | **0.324** | 4,169 |
| D00 | longitudinal crack | 0.689 | 0.391 | 1,662 |
| D10 | transverse crack | 0.594 | 0.282 | 921 |
| D20 | alligator crack | **0.705** | 0.376 | 983 |
| D40 | pothole | 0.555 | 0.248 | 603 |

Cracks (D00, D20) detected best. Potholes (D40) and transverse cracks (D10) weakest — suggests class imbalance and/or harder visual signature. Worth a per-class weighted loss in a future round.

## Per-country breakdown (mAP@0.5)

| Country | mAP@0.5 | Test images | Notes |
|---|---:|---:|---|
| **China (MotorBike)** | **0.889** | 181 | Distinctive motorbike-cam perspective; easiest |
| United States | 0.616 | 496 | Mid-range |
| Japan | 0.600 | 776 | Largest test slice |
| Czech | 0.473 | 118 | Different road textures |
| **India** | **0.375** | 334 | Most diverse damage types; hardest |

**Range: 0.514 (0.889 − 0.375).** Cross-country transfer is the real story here, not aggregate mAP. A model trained on uniform-distribution train data (which includes all 5 countries) still varies wildly by country at test time.

## Training trajectory

```
Epoch  mAP@0.5  mAP@0.5:0.95
   1   0.118    0.041
   2   0.208    0.080
   3   0.231    0.092
   4   0.298    0.120
   5   0.306    0.130
   6   0.316    0.132
   7   0.398    0.182   ← step jump
   8   0.414    0.192
   9   0.433    0.200
  10   0.457    0.212
  11   0.434    0.198   ← noise, dipped slightly
  12   0.487    0.228
  13   0.496    0.236
  14   0.516    0.245   ← crossed 0.5
  15   0.527    0.252
  16   0.538    0.264
  17   0.545    0.266
  18   0.554    0.271
  19   0.557    0.275
  20   0.587    0.294
  21   0.579    0.292
  22   0.593    0.300
  23   0.599    0.305
  24   0.604    0.308   ← crossed 0.6
  25   0.617    0.315
  26   0.616    0.316
  27   0.623    0.319
  28   0.629    0.325
  29   0.631    0.325
  30   0.631    0.325   ← plateaued
post  0.632    0.325   ← final val pass on best.pt
```

Smooth descent. Step jump at epoch 7 (0.316 → 0.398). Plateaued cleanly around epoch 25-30. No overfit signature in the 30-epoch budget. Could push further with longer schedule + cosine LR but diminishing returns.

## What this means for the interview

**This is competitive with single-model published baselines on RDD2022.** Challenge winners typically report 0.55–0.70 mAP@0.5 (often with ensembles + heavy augmentation). Our 0.636 with no tuning and 30 epochs sits in the middle of that range.

**The cross-country gap is the talking point.** Bluemap operates on Swiss roads. RDD2022 doesn't include Switzerland. The 0.51-point spread between China and India shows the domain-shift problem is real and quantifiable. A candidate who walks in with this number AND explains why mAP isn't the right business metric (recall on road segments, calibrated severity, cross-domain robustness) reframes the conversation.

**Latency (11.3 ms median on A10G) is real-time.** Bluemap's pipeline ingests street-level imagery from car-mounted cameras; a model that can run at >80 fps comfortably on a single mid-range GPU is operationally trivial.

## What's preserved

- `best.pt` (40.5 MB) on Modal volume `rdd2022/runs/baseline/weights/best.pt`
- `eval_report.json` on the same volume with all numbers above
- Full training run history in `rdd2022/runs/baseline/results.csv`
- Reproducibility: re-running the same pipeline (`download_rdd2022.py` → `train_modal.py` → `eval_modal.py`) is fully deterministic given the seed-based 80/10/10 split

## What Day 3+ adds

Day 3 sweep (≤ 1 day):
- Per-class loss weighting (boost D40 / D10)
- Longer schedule (50 epochs cosine LR) to push past 0.65
- Test-time augmentation (TTA) for + ~2-3 mAP

Day 6-7: VLM hybrid (Qwen2-VL or Llama-3.2-Vision) for high-recall coarse classification + severity. The right business-metric story.

Day 8-9: Calibration. Temperature-scaled confidences, reliability diagrams, threshold picking by target precision/recall.

Day 10: Active learning. Use uncertainty to rank "next 50 images that would teach the model the most."

Day 11-12: GeoPulse integration. Drop the trained YOLO11m into `ml/`, replace COCO Mask R-CNN, demo on a Swiss street image.

Day 13-14: Demo polish + writeup + interview rehearsal.

Roadmap fits comfortably before June 1.
