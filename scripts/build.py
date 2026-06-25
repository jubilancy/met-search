#!/usr/bin/env python3
"""
build.py — Builds artworks.json for the Met Search frontend.

Steps:
  1. Download MetObjects.csv from the Met's GitHub LFS
  2. Filter to public domain records that have a Link Resource (object ID)
  3. Hit the Met Collection API for each object to get primaryImageSmall
  4. Write data/artworks.json

This is designed to run in GitHub Actions on a weekly schedule.
It's rate-limited to ~80 req/s to be polite to the Met API.
Expected runtime: ~3-5 hours for ~180k records (first run).
Subsequent runs skip objects already in the existing JSON.
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

CSV_URL = "https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv"
API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1/objects/"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "artworks.json"

# Fields to pull from the CSV
CSV_FIELDS = [
    "Object ID",
    "Title",
    "Artist Display Name",
    "Artist Display Bio",
    "Object Date",
    "Object Begin Date",
    "Object End Date",
    "Medium",
    "Dimensions",
    "Culture",
    "Period",
    "Dynasty",
    "Department",
    "Classification",
    "Credit Line",
    "Country",
    "City",
    "Link Resource",
    "Is Highlight",
    "Tags",
]

RATE_LIMIT_DELAY = 0.05  # 50ms between requests (~20 req/s, well under their limit)
API_TIMEOUT = 10
MAX_RETRIES = 3


def download_csv(path: Path):
    print(f"Downloading MetObjects.csv from GitHub LFS...")
    print(f"  → {CSV_URL}")
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "met-search-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        content = response.read().decode("utf-8")
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ Saved to {path} ({len(content) // 1024 // 1024} MB)")


def load_existing(output_path: Path) -> dict:
    """Load existing artworks.json to enable incremental builds."""
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        indexed = {str(a["id"]): a for a in existing}
        print(f"  ✓ Loaded {len(indexed)} existing records (incremental mode)")
        return indexed
    return {}


def fetch_image_url(object_id: str) -> str | None:
    url = API_BASE + object_id
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "met-search-builder/1.0"})
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
                data = json.loads(response.read())
                img = data.get("primaryImageSmall") or data.get("primaryImage")
                return img if img else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    return None


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV and return public domain records with a Link Resource."""
    records = []
    print(f"Parsing {csv_path.name}...")
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Is Public Domain", "").strip().lower() != "true":
                continue
            link = row.get("Link Resource", "").strip()
            if not link:
                continue
            obj_id = row.get("Object ID", "").strip()
            if not obj_id:
                continue
            records.append({k: row.get(k, "").strip() for k in CSV_FIELDS})
    print(f"  ✓ {len(records)} public domain records with object IDs")
    return records


def build(skip_api: bool = False):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    csv_path = Path("/tmp/MetObjects.csv")

    # Download CSV
    if not csv_path.exists():
        download_csv(csv_path)
    else:
        print(f"  ✓ Using cached CSV at {csv_path}")

    # Load existing index for incremental builds
    existing = load_existing(OUTPUT_PATH)

    # Parse CSV
    records = parse_csv(csv_path)

    artworks = []
    skipped = 0
    fetched = 0
    no_image = 0

    print(f"\nEnriching {len(records)} records with image URLs...")
    print(f"  (skipping {len(existing)} already indexed)\n")

    for i, row in enumerate(records):
        obj_id = row["Object ID"]

        # Reuse existing if already fetched
        if obj_id in existing:
            artworks.append(existing[obj_id])
            skipped += 1
            continue

        if not skip_api:
            time.sleep(RATE_LIMIT_DELAY)
            image_url = fetch_image_url(obj_id)
        else:
            image_url = None

        if not image_url and not skip_api:
            no_image += 1
            continue  # Skip objects with no image

        artwork = {
            "id": int(obj_id),
            "title": row["Title"] or "Untitled",
            "artist": row["Artist Display Name"],
            "artistBio": row["Artist Display Bio"],
            "date": row["Object Date"],
            "dateBegin": int(row["Object Begin Date"]) if row["Object Begin Date"].lstrip("-").isdigit() else None,
            "dateEnd": int(row["Object End Date"]) if row["Object End Date"].lstrip("-").isdigit() else None,
            "medium": row["Medium"],
            "dimensions": row["Dimensions"],
            "culture": row["Culture"],
            "period": row["Period"],
            "dynasty": row["Dynasty"],
            "department": row["Department"],
            "classification": row["Classification"],
            "creditLine": row["Credit Line"],
            "country": row["Country"],
            "city": row["City"],
            "tags": row["Tags"],
            "isHighlight": row["Is Highlight"].lower() == "true",
            "url": row["Link Resource"],
            "image": image_url,
        }
        artworks.append(artwork)
        fetched += 1

        # Progress + periodic save
        if (i + 1) % 1000 == 0:
            pct = (i + 1) / len(records) * 100
            print(f"  [{pct:5.1f}%] {i+1}/{len(records)} — {fetched} fetched, {skipped} cached, {no_image} skipped (no image)")
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(artworks, f, ensure_ascii=False, separators=(",", ":"))

    # Final write
    print(f"\nWriting {len(artworks)} artworks to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(artworks, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print(f"  ✓ Done — {len(artworks)} artworks, {size_mb:.1f} MB")
    print(f"  ✓ Fetched: {fetched}, Cached: {skipped}, No image (skipped): {no_image}")


if __name__ == "__main__":
    skip_api = "--no-api" in sys.argv
    build(skip_api=skip_api)
