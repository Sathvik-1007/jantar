"""Download the entire data.gov.in API catalog (285K+ resources).

Uses curl subprocess because Python httpx/requests time out on data.gov.in
(server HTTP/2 + TLS config incompatible with Python 3.13 SSL).

Usage:
    python scripts/download_catalog.py

Outputs:
    data/catalog/data_gov_in_full.jsonl  — raw catalog (one JSON per line)
    data/catalog/data_gov_in_clean.json  — filtered, deduplicated, searchable
    data/catalog/stats.json             — download statistics
"""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CATALOG_URL = "https://api.data.gov.in/lists"
PAGE_SIZE = 1000
OUT_DIR = Path(__file__).parent.parent / "data" / "catalog"
WORKERS = 8


def fetch_page(offset: int) -> list[dict]:
    """Fetch one page via curl (bypasses Python TLS issues)."""
    url = f"{CATALOG_URL}?format=json&offset={offset}&limit={PAGE_SIZE}"
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "30", url],
                capture_output=True, text=True, timeout=35,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return data.get("records", [])
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        time.sleep(1 * (attempt + 1))
    return []


def get_total() -> int:
    """Get total count from first request."""
    url = f"{CATALOG_URL}?format=json&offset=0&limit=1"
    result = subprocess.run(
        ["curl", "-s", "--max-time", "15", url],
        capture_output=True, text=True, timeout=20,
    )
    data = json.loads(result.stdout)
    return int(data["total"])


def clean_catalog(records: list[dict]) -> list[dict]:
    """Filter and deduplicate. Keep only useful, public APIs."""
    seen = set()
    clean = []
    skip_words = {"sample data", "test ", "demo ", "testing", "untitled"}

    for r in records:
        idx = r.get("index_name", "")
        title = r.get("title", "").strip()
        desc = r.get("desc", "").strip()

        if not idx or not title or idx in seen:
            continue
        if len(title) < 5:
            continue
        if any(s in title.lower() for s in skip_words):
            continue

        seen.add(idx)
        fields = [f.get("name", "") for f in r.get("field", []) if f.get("name")]

        clean.append({
            "id": idx,
            "title": title,
            "description": desc,
            "source": r.get("source", ""),
            "org_type": r.get("org_type", ""),
            "fields": fields[:20],  # Cap at 20 field names for embedding efficiency
            "updated": r.get("updated_date", ""),
        })

    return clean


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("data.gov.in Full Catalog Download")
    print("=" * 60)

    total = get_total()
    print(f"Total resources on platform: {total:,}")

    offsets = list(range(0, total, PAGE_SIZE))
    print(f"Pages to fetch: {len(offsets)} (size={PAGE_SIZE}, workers={WORKERS})")

    all_records = []
    start = time.time()

    # Parallel download with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_page, off): off for off in offsets}
        done_count = 0
        for future in as_completed(futures):
            records = future.result()
            all_records.extend(records)
            done_count += 1
            if done_count % 10 == 0:
                elapsed = time.time() - start
                pct = done_count / len(offsets) * 100
                rate = len(all_records) / elapsed
                eta = (total - len(all_records)) / rate if rate > 0 else 0
                print(
                    f"  [{pct:5.1f}%] {len(all_records):,}/{total:,} "
                    f"| {elapsed:.0f}s elapsed | ETA {eta:.0f}s | {rate:.0f} rec/s"
                )

    elapsed = time.time() - start
    print(f"\nDownloaded {len(all_records):,} records in {elapsed:.0f}s")

    # Save raw (one JSON per line for streaming)
    raw_path = OUT_DIR / "data_gov_in_full.jsonl"
    with open(raw_path, "w") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")
    size_mb = raw_path.stat().st_size / 1024 / 1024
    print(f"Raw catalog: {raw_path} ({size_mb:.1f} MB)")

    # Clean
    clean = clean_catalog(all_records)
    clean_path = OUT_DIR / "data_gov_in_clean.json"
    with open(clean_path, "w") as f:
        json.dump(clean, f)
    size_mb = clean_path.stat().st_size / 1024 / 1024
    print(f"Clean catalog: {clean_path} ({len(clean):,} APIs, {size_mb:.1f} MB)")

    # Stats
    orgs = {}
    for r in clean:
        org = r.get("org_type", "Unknown")
        if isinstance(org, list):
            org = org[0] if org else "Unknown"
        orgs[org] = orgs.get(org, 0) + 1

    stats = {
        "total_on_platform": total,
        "downloaded": len(all_records),
        "after_cleaning": len(clean),
        "download_seconds": round(elapsed),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "org_types": dict(sorted(orgs.items(), key=lambda x: -x[1])),
    }
    stats_path = OUT_DIR / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\nStats:")
    for org, count in sorted(orgs.items(), key=lambda x: -x[1])[:10]:
        print(f"  {org}: {count:,}")
    print(f"\nDone. Run `python scripts/ingest_catalog.py` to index into Qdrant.")


if __name__ == "__main__":
    main()
