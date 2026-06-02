# GeoPulse demo — cheat sheet

Open it: `https://geopulse.igaspar.com` (or `http://localhost:8085` from your laptop).

---

## What this thing actually is

A **review console for road-damage detections**. A model looked at 15 real road photos (from a public dataset) and drew boxes around what it thinks are cracks and potholes. The map shows where each detection "happened"; clicking a marker shows the photo with the model's box on it, plus a Confirm / Reject button. That's the human-in-the-loop part — the model proposes, a person confirms.

Three pieces:

- **Frontend** (React + MapLibre): the map + filters + the review panel.
- **Backend** (ASP.NET Core): a thin REST API that hands defects to the frontend and accepts confirm/reject updates.
- **ML side** (Python + PyTorch + ultralytics): the trained model. You ran it once, it wrote a `report.json`, the backend loads that file at startup and turns each detection into a "defect" on the map.

There's no live inference in the demo. The model already ran; the demo plays back the results.

## What model is running, in plain English

- **YOLO11m**: a recent image-detector architecture from ultralytics. "11" is the version, "m" is medium size (~20M parameters). Real-time speed on a mid-range GPU.
- **RDD2022**: the public Road Damage Detection dataset. 47,420 labelled photos from China, Japan, India, US, Czech. 4 damage classes:
  - **D00** — longitudinal crack (runs along the road)
  - **D10** — transverse crack (runs across the road)
  - **D20** — alligator crack (network of cracks, like crocodile skin)
  - **D40** — pothole
- **Trained on Modal** (serverless GPU) for ~4 hours on an A10G. Cost: ~$5.50.

## mAP — the one metric people ask about

**mAP** = "mean Average Precision". A single 0-to-1 number that summarises how well an object detector finds and locates things. Higher = better.

The slow walk-through:

- For each detection the model produces, you compare its box to a "true" box from the labels. If they overlap enough — usually IoU ≥ 0.5 (more on IoU below) — it counts as a hit.
- For each class (cracks, potholes, etc.), you compute the **precision-recall curve** (how many of the model's guesses were right vs. how many true defects it found). The area under that curve is the **Average Precision** for that class.
- Average across classes → **mean Average Precision** = mAP.
- **mAP@0.5** = require boxes to overlap by 50% to count as a hit. Lenient.
- **mAP@0.5:0.95** = average mAP over 10 stricter overlap thresholds (0.5, 0.55, …, 0.95). Much harder. Always lower.

**Your numbers (RDD2022 test set, 4169 defects):**
- mAP@0.5 = **0.636**
- mAP@0.5:0.95 = **0.324**
- Published RDD2022 challenge winners typically land at 0.55–0.70 mAP@0.5, often with ensembles + heavy data augmentation. Your single-model, 30-epoch, no-tuning baseline at 0.636 is competitively in that band.

**IoU** = "Intersection over Union". If two boxes overlap, IoU is (overlap area) / (combined area). 1.0 = perfect overlap, 0 = no overlap. The 0.5 threshold means "the box has to be in roughly the right place and roughly the right size."

If someone asks "why not just accuracy?": detection has no "correct count" denominator — an image can have 0 or 50 defects. Precision/recall against IoU is the standard answer.

## The cross-country point (the real story)

Train data: 80% of all images mixed across 5 countries. Test data: 20% held out, also mixed. So the model sees all countries during training.

**But mAP@0.5 by country on the test set:**
| Country | mAP@0.5 |
|---|---:|
| China (MotorBike cam) | **0.889** |
| United States | 0.616 |
| Japan | 0.600 |
| Czech | 0.473 |
| **India** | **0.375** |

That's a **0.514 point spread** for the same model on the same task. The model didn't get worse — the *roads got harder*. India images have more diverse damage types, dustier conditions, more complex backgrounds. China_MotorBike has a distinctive low motorbike-cam perspective that's easy to learn.

**Why this matters for a Swiss customer:** Switzerland isn't in RDD2022. So before deploying this on a Swiss mobile-mapping run, you have to assume real-world Swiss performance lands somewhere on this 0.375–0.889 spread — and you need to know where. That's a sales conversation about pilot data, not a model number.

This is the talking point that makes you sound like you've actually thought about deployment vs. just "the model scored X."

## Confidence — why it's not a probability

The scores you see (`0.77`, `0.45`, etc.) are the model's raw output, not calibrated probabilities. A "0.77" doesn't mean "77% chance this is a real crack." It just means "more confident than 0.5, less confident than 0.9."

To turn it into a real probability you'd run **calibration**: temperature scaling on a held-out set, or isotonic regression, then a reliability diagram to verify. We didn't do that here.

**Why I care:** if a customer says "show me everything we're ≥80% sure about", you can't deliver that from raw scores. The slider in the UI is a *ranking* tool, not a probability filter. Acknowledging this in the demo signals you understand what production-grade looks like.

## Demo script (5 minutes)

1. **Open the page.** Five blue clusters around Burgdorf. Say: *"Each cluster is a country slice from the RDD2022 test set — China, Japan, US, Czech, India. The model ran over 15 real road photos; these 25 markers are what it found."*

2. **Read the left sidebar.** *"YOLO11m fine-tuned on RDD2022, four classes — longitudinal/transverse/alligator cracks and potholes. mAP at 0.5 of 0.636 — that's the literature-band number. 11ms per image on an A10G GPU — real-time."*

3. **Click a China_MotorBike cluster marker.** Photo + tight red box on an obvious crack. *"Clean detection. China was the easiest slice — 0.89 mAP. Distinctive camera perspective the model latched onto."*

4. **Click an India cluster marker.** Probably a noisier box or a duplicate. *"Same model, harder slice. 0.38 mAP. More damage types, busier scenes, dirt roads. The model is the same — the **domain** is different."*

5. **Move the confidence slider.** *"This is filtering by raw model score, not calibrated probability. To productionise we'd add temperature scaling and verify with a reliability diagram. The slider is for ranking, not for a probability cutoff."*

6. **Click Confirm on a true detection, Reject on a noisy one.** *"This is the human-in-the-loop part — backend writes the status, what would feed an active-learning loop where the model retrains on cases the human caught."*

## Questions you should expect

**"What about Switzerland?"** — Swiss roads aren't in RDD2022. The cross-country spread suggests Swiss performance will land somewhere between 0.4 and 0.9; we'd run a 200-image pilot first to localise that.

**"Why YOLO and not Mask R-CNN / Transformer?"** — YOLO11m gives detection (boxes) at ~11ms/image. Mask R-CNN adds per-pixel masks but is 3-5x slower; we don't need masks for a "where's the damage" use case. Transformers (DETR family) match YOLO accuracy but are heavier to deploy.

**"How much would it cost to retrain on Swiss data?"** — Training cost was $5.50 on a public dataset. Doubling that for Swiss fine-tuning is ~$12 in compute. The expensive part is *labelling* — ~$0.50–$2 per image annotated, so 5000 images = $2.5–10k.

**"How would you deploy this at scale?"** — Inference goes onto edge devices in the mapping vehicles (a Jetson can run YOLO11m comfortably) or batch on a central GPU. The review UI is the same; you'd just swap the file-based report for a streaming ingest endpoint.

**"Why 0.636 — is that good?"** — RDD2022 challenge winners report 0.55–0.70 mAP@0.5 with ensembles + heavy augmentation. Our single-model 30-epoch baseline at 0.636 is in that band with none of that. There's headroom — longer schedule (50 epochs), test-time augmentation, per-class loss weighting would push it past 0.65.

**"Why don't the markers correspond to real road locations?"** — They don't. We don't have camera pose / GPS for the RDD2022 images. The lat/lng is a stand-in: each country slice is dropped near Burgdorf so you see five clusters on the map. A real pipeline projects each bbox to a world coordinate using camera intrinsics + GNSS/IMU.

## Things to *not* say

- Don't say "the model is 64% accurate" — mAP isn't accuracy. Say "the model scored 0.636 mAP@0.5."
- Don't say "the model is 77% confident this is a real crack" — raw scores aren't calibrated probabilities. Say "the model's score is 0.77 — that's a ranking, not a probability."
- Don't claim "we'd see the same performance on Swiss roads." Say the opposite — domain transfer is the open question.

## If something breaks during the demo

- **Map empty:** `docker compose restart api` and refresh. The api reads `ml/report.json` at startup; if you regenerate it, you must restart.
- **Tunnel down:** check `Get-Service cloudflared` in PowerShell, `Start-Service cloudflared` if it's stopped. Local fallback is always `http://localhost:8085/`.
- **Stack down:** `docker compose ps` from the GeoPulse dir, `docker compose up -d` to start anything that's stopped.
- **You panic:** screenshot the page beforehand and have it open as a fallback. (`geopulse-clusters.png` in the repo root.)
