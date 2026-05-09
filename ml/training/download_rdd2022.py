"""Download RDD2022, convert Pascal VOC -> YOLO format, write to Modal volume.

Runs on Modal (good bandwidth + persistent volume). One-shot operation.

Source: official IEEE Big Data 2022 RDD challenge dataset, hosted as
country-zip files on the sekilab/RoadDamageDetector GitHub release.

After this completes the Modal volume `rdd2022` contains:
  /vol/rdd2022/
    images/{train,val,test}/{country}_*.jpg
    labels/{train,val,test}/{country}_*.txt   (YOLO format)
    rdd2022.yaml                              (ultralytics dataset config)
    download_summary.json                     (counts, splits, sources)

Run:
    set -a; . ~/Development/Base/eidos/.env; set +a   # for MODAL_TOKEN_*
    export PYTHONIOENCODING=utf-8
    uv run --project ml modal run ml/training/download_rdd2022.py
"""

import json
import modal

app = modal.App("geopulse-rdd2022-download")

vol = modal.Volume.from_name("rdd2022", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("wget", "unzip")
    .pip_install("tqdm>=4.66")
)

# RDD2022 country-zip URLs (CRDDC2022 official S3 mirror).
# Skipping Norway (9.9 GB) for the baseline; the other 5 total ~2.4 GB.
# Re-add Norway later if cross-domain story needs it.
_S3_BASE = "https://bigdatacup.s3.ap-northeast-1.amazonaws.com/2022/CRDDC2022/RDD2022/Country_Specific_Data_CRDDC2022"
COUNTRY_URLS = {
    "Japan":           f"{_S3_BASE}/RDD2022_Japan.zip",            # 1022 MB
    "India":           f"{_S3_BASE}/RDD2022_India.zip",            #  502 MB
    "Czech":           f"{_S3_BASE}/RDD2022_Czech.zip",            #  245 MB
    "United_States":   f"{_S3_BASE}/RDD2022_United_States.zip",    #  424 MB
    "China_MotorBike": f"{_S3_BASE}/RDD2022_China_MotorBike.zip",  #  183 MB
    # "Norway":        f"{_S3_BASE}/RDD2022_Norway.zip",           # 9.9 GB — skipped
}

# Canonical 4-class taxonomy used in the IEEE Big Data 2022 challenge.
# Ignore other RDD2022 sub-types to keep the baseline well-defined.
CANONICAL_CLASSES = ["D00", "D10", "D20", "D40"]
CLASS_TO_ID = {name: i for i, name in enumerate(CANONICAL_CLASSES)}

# Per-sample stratified split. Same fraction across countries.
TRAIN_FRAC = 0.80
VAL_FRAC = 0.10
# remaining 0.10 -> test


@app.function(
    image=image,
    timeout=2 * 3600,  # 2 hours; downloads + conversion
    volumes={"/vol": vol},
)
def download_and_convert():
    import hashlib
    import os
    import random
    import shutil
    import subprocess
    import xml.etree.ElementTree as ET
    from pathlib import Path

    target_root = Path("/vol/rdd2022")
    images_root = target_root / "images"
    labels_root = target_root / "labels"
    for split in ("train", "val", "test"):
        (images_root / split).mkdir(parents=True, exist_ok=True)
        (labels_root / split).mkdir(parents=True, exist_ok=True)

    cache_root = Path("/tmp/rdd2022_cache")
    cache_root.mkdir(parents=True, exist_ok=True)

    summary = {
        "countries": {},
        "splits": {"train": 0, "val": 0, "test": 0},
        "classes": CANONICAL_CLASSES,
        "errors": [],
    }

    for country, url in COUNTRY_URLS.items():
        print(f"\n=== {country} ===")
        country_zip = cache_root / f"{country}.zip"
        if not country_zip.exists():
            print(f"  downloading {url}")
            res = subprocess.run(
                ["wget", "-q", "--show-progress", "-O", str(country_zip), url],
                check=False,
            )
            if res.returncode != 0 or country_zip.stat().st_size < 1_000_000:
                print(f"  FAILED to download {country}; skipping")
                summary["errors"].append(f"download_failed:{country}")
                country_zip.unlink(missing_ok=True)
                continue
            print(f"  downloaded {country_zip.stat().st_size / 1e6:.1f} MB")
        else:
            print(f"  cached: {country_zip}")

        country_extract = cache_root / country
        if not country_extract.exists():
            print(f"  extracting...")
            country_extract.mkdir(exist_ok=True)
            res = subprocess.run(
                ["unzip", "-q", "-o", str(country_zip), "-d", str(country_extract)],
                check=False,
            )
            if res.returncode != 0:
                summary["errors"].append(f"unzip_failed:{country}")
                continue

        # Find images and annotations within the extracted tree.
        # RDD2022 layout per country: <country>/train/{images,annotations/xmls}/
        train_images_dirs = list(country_extract.rglob("train/images"))
        train_xmls_dirs = list(country_extract.rglob("train/annotations/xmls"))
        if not train_images_dirs or not train_xmls_dirs:
            print(f"  layout unexpected for {country}; check {country_extract}")
            summary["errors"].append(f"layout_unexpected:{country}")
            continue
        images_src = train_images_dirs[0]
        xmls_src = train_xmls_dirs[0]
        print(f"  images: {images_src}")
        print(f"  xmls:   {xmls_src}")

        image_paths = sorted(images_src.glob("*.jpg")) + sorted(images_src.glob("*.JPG"))
        if not image_paths:
            summary["errors"].append(f"no_images:{country}")
            continue

        # Stratified random split by image filename hash (deterministic).
        country_counts = {"train": 0, "val": 0, "test": 0, "kept": 0, "skipped_no_xml": 0}
        for img_path in image_paths:
            stem = img_path.stem
            xml_path = xmls_src / f"{stem}.xml"
            if not xml_path.exists():
                country_counts["skipped_no_xml"] += 1
                continue

            # Deterministic split via hash; 80/10/10.
            h = int(hashlib.md5(stem.encode()).hexdigest(), 16) / (16 ** 32)
            if h < TRAIN_FRAC:
                split = "train"
            elif h < TRAIN_FRAC + VAL_FRAC:
                split = "val"
            else:
                split = "test"

            # Convert XML to YOLO label.
            label_lines = _xml_to_yolo(xml_path)
            if label_lines is None:
                country_counts["skipped_no_xml"] += 1
                continue
            # Skip images with zero canonical-class boxes.
            if not label_lines:
                continue

            # Filenames: prefix with country to avoid collisions across countries.
            target_name = f"{country}_{stem}"
            target_img = images_root / split / f"{target_name}.jpg"
            target_lbl = labels_root / split / f"{target_name}.txt"
            if not target_img.exists():
                shutil.copy(img_path, target_img)
            target_lbl.write_text("\n".join(label_lines))
            country_counts[split] += 1
            country_counts["kept"] += 1

        for split in ("train", "val", "test"):
            summary["splits"][split] += country_counts[split]
        summary["countries"][country] = country_counts
        print(
            f"  kept {country_counts['kept']} (train {country_counts['train']}, "
            f"val {country_counts['val']}, test {country_counts['test']}); "
            f"skipped {country_counts['skipped_no_xml']} without XML"
        )

    # Write the YOLO dataset YAML.
    yaml_path = target_root / "rdd2022.yaml"
    yaml_path.write_text(
        "# Auto-generated by download_rdd2022.py\n"
        f"path: /vol/rdd2022\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"test: images/test\n"
        f"nc: {len(CANONICAL_CLASSES)}\n"
        f"names: {CANONICAL_CLASSES}\n"
    )
    print(f"\nwrote {yaml_path}")

    # Persist summary and commit volume.
    (target_root / "download_summary.json").write_text(json.dumps(summary, indent=2))
    vol.commit()
    print(f"\nsplits: {summary['splits']}")
    print(f"errors: {summary['errors']}")
    return summary


def _xml_to_yolo(xml_path):
    """Parse a Pascal VOC XML; return list of YOLO lines for canonical classes only.

    Returns None if XML is malformed; empty list if no canonical-class boxes.
    """
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    root = tree.getroot()
    size = root.find("size")
    if size is None:
        return None
    w = int(size.findtext("width") or 0)
    h = int(size.findtext("height") or 0)
    if w <= 0 or h <= 0:
        return None

    lines = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip()
        if name not in CLASS_TO_ID:
            continue
        cid = CLASS_TO_ID[name]
        bb = obj.find("bndbox")
        if bb is None:
            continue
        try:
            xmin = float(bb.findtext("xmin"))
            ymin = float(bb.findtext("ymin"))
            xmax = float(bb.findtext("xmax"))
            ymax = float(bb.findtext("ymax"))
        except (TypeError, ValueError):
            continue
        if xmax <= xmin or ymax <= ymin:
            continue
        cx = ((xmin + xmax) / 2) / w
        cy = ((ymin + ymax) / 2) / h
        bw = (xmax - xmin) / w
        bh = (ymax - ymin) / h
        if not (0 < bw <= 1 and 0 < bh <= 1):
            continue
        lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return lines


@app.local_entrypoint()
def main():
    summary = download_and_convert.remote()
    print("\n=== Download complete ===")
    print(json.dumps(summary, indent=2))
