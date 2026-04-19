# geopulse-ml

Companion to GeoPulse. Takes a street-level image, proposes detections with a
pretrained Mask R-CNN (COCO weights), asks a human to confirm each, and writes
a JSON report.

This mirrors the shape of `digital survey`'s **Infrastruktur-Inventarisierung**
and **Strassenschild-Erkennung** workflows: model proposes, surveyor confirms,
GIS stores the reviewed record.

## Shape, not accuracy

The pretrained COCO weights recognise stop signs, traffic lights, cars, etc.
They are **not** trained for Swiss road damage, pavement cracks, or VSS
feature classes. This project demonstrates the **pipeline shape** — replace
the model in `detect.py` with a domain-specific checkpoint to make it useful.

Note on confidence: Mask R-CNN softmax outputs are not probability-calibrated.
The default 0.5 threshold is a modelling convention, not a statement about
ground truth. For a reviewer UI, temperature scaling on a held-out set is a
more honest source of triage thresholds.

## Run it

```bash
cd ml
uv sync                     # first run downloads torch + torchvision
uv run geopulse-ml path/to/street.jpg
```

First inference run will pull ~170 MB of COCO weights into PyTorch's cache.

Options:

- `--score-threshold 0.3` — loosen the detector (more proposals, more noise)
- `--classes "stop sign" --classes "traffic light"` — restrict COCO classes
- `--output report.json` — where to write the review record
- `--annotated annotated.jpg` — annotated preview with numbered boxes
- `--center-lat 47.0609 --center-lng 7.6250 --radius-m 300` — where to scatter the
  pretend survey run (defaults are Burgdorf)

Review loop prompts `y` / `n` / `s` (accept / reject / flag for later).
Accepted and flagged detections get a lat/lng sampled uniformly inside a disc
of `radius_m` around the configured centre — a stand-in for the real
bbox→world projection a production pipeline would do with camera pose + GNSS/IMU.

## Output

`report.json`:

```json
{
  "source_image": "...",
  "model": "torchvision.maskrcnn_resnet50_fpn.COCO_V1",
  "generated_at": "2026-04-19T09:12:43+00:00",
  "survey_run": { "center_lat": 47.0609, "center_lng": 7.6250, "radius_m": 300 },
  "score_threshold": 0.5,
  "kept_classes": ["fire hydrant", "stop sign", "traffic light"],
  "detections": [
    {
      "id": 1,
      "label": "stop sign",
      "score": 0.93,
      "bbox": [412.1, 188.4, 466.0, 241.7],
      "status": "accepted",
      "latitude": 47.0613,
      "longitude": 7.6254
    }
  ]
}
```

## How it feeds the reviewer UI

The `.NET` backend looks for `report.json` at `../../ml/report.json` on
startup (overridable via the `MlReportPath` config key). Accepted and flagged
detections are converted into `Defect` records and spliced into the seeded
store:

- `label` → `type` (COCO `stop sign` → `Sign`, `traffic light` → `TrafficLight`,
  `fire hydrant` → `Hydrant`, anything else → `Damage`)
- `score` → `confidence`, bucketed into `severity` (≥0.85 high, ≥0.65 medium, else low)
- `status: accepted` → `Confirmed`, `needs_review` → `New`
- `latitude` / `longitude` → the map position

Restart the backend after re-running the CLI to pick up the new report.

## Where this would grow

- Swap Mask R-CNN for a domain-specific detector (e.g. a crack-segmentation
  model fine-tuned on RDD2022 or similar).
- Replace the disc-sampled lat/lng with a real bbox→world projection using
  camera intrinsics and pose from GNSS/IMU.
- Replace the restart-on-change flow with an actual ingest endpoint on the
  backend so the report streams in without bouncing the service.
