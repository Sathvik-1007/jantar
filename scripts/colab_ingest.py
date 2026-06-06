"""
Jantar — Colab Ingest Script (Self-Contained)
==============================================
Paste this ENTIRE script into a Colab cell.
Upload ONLY: data_gov_in_deduped.json.gz (10 MB) or data_gov_in_deduped.json (109 MB)

On T4 (free): ~25 min | On A100: ~8 min

USAGE:
  1. Upload data_gov_in_deduped.json.gz to the Colab runtime
  2. Set QDRANT_URL below to your Qdrant server
  3. Run this cell
"""

import gzip, json, os, sys, time

# ─── CONFIG (EDIT THESE) ──────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "")  # SET THIS or env var
COLLECTION = "tool_vectors"
CATALOG_FILE = "data_gov_in_deduped.json.gz"  # .gz or .json both work
BATCH_SIZE = 128    # T4=128, A100=256
VECTOR_DIM = 1024

if not QDRANT_URL:
    print("ERROR: Set QDRANT_URL before running.")
    print("  Option 1: QDRANT_URL = 'http://YOUR_IP:6333'")
    print("  Option 2: os.environ['QDRANT_URL'] = 'http://YOUR_IP:6333'")
    sys.exit(1)

# ─── CUSTOM TOOL SPECS (government services + citizen utilities — inlined) ─────
CUSTOM_SPECS = [
    {"name": "open_meteo_weather", "source": "api.open-meteo.com", "description": "Current weather and 7-day forecast for any Indian city. Temperature, humidity, rain, wind. Free, no API key.", "domain": "weather", "endpoint": "https://api.open-meteo.com/v1/forecast", "examples": ["What's the weather in Delhi?", "दिल्ली का मौसम कैसा है?", "Will it rain tomorrow in Mumbai?"]},
    {"name": "open_meteo_air_quality", "source": "air-quality-api.open-meteo.com", "description": "Real-time air quality (AQI, PM2.5, PM10, NO2, SO2, O3) for any Indian location. Free, no API key.", "domain": "environment", "endpoint": "https://air-quality-api.open-meteo.com/v1/air-quality", "examples": ["Air quality in Delhi today", "दिल्ली में प्रदूषण कितना है?", "PM2.5 level in Mumbai"]},
    {"name": "open_meteo_historical_weather", "source": "archive-api.open-meteo.com", "description": "Historical weather data for any Indian location from 1940 to present. Free, no key.", "domain": "weather", "endpoint": "https://archive-api.open-meteo.com/v1/archive", "examples": ["Rainfall in Mumbai last monsoon?", "पिछले साल दिल्ली में कितनी गर्मी पड़ी?"]},
    {"name": "india_post_pincode", "source": "api.postalpincode.in", "description": "Post office details by PIN code or branch name search. Branch, delivery status, district, state. Government postal service. Free, no API key.", "domain": "postal", "endpoint": "https://api.postalpincode.in/pincode/{pincode}", "examples": ["Which post office serves PIN 110001?", "पिन कोड 400001 का डाकघर?"]},
    {"name": "razorpay_ifsc", "source": "ifsc.razorpay.com", "description": "Bank branch details by IFSC code. Bank name, branch, address, city, district, state, MICR code. RBI-regulated banking infrastructure. Free, no API key.", "domain": "banking", "endpoint": "https://ifsc.razorpay.com/{ifsc}", "examples": ["What bank has IFSC SBIN0001234?", "IFSC कोड HDFC0000001 का बैंक?"]},
    {"name": "sarvam_translate", "source": "api.sarvam.ai", "description": "Translate between 22 Indian languages and English using Sarvam AI. Hindi, Bengali, Tamil, Telugu, Marathi, etc.", "domain": "language", "endpoint": "https://api.sarvam.ai/translate", "examples": ["Translate this to Hindi", "इसे English में translate करो"]},
    {"name": "sarvam_stt", "source": "api.sarvam.ai", "description": "Speech/audio to text. 23 Indian languages with auto-detection. Handles accents and code-mixing.", "domain": "language", "endpoint": "https://api.sarvam.ai/speech-to-text", "examples": ["Convert audio to text", "ऑडियो को टेक्स्ट में बदलो"]},
]

# ─── FUNCTIONS ────────────────────────────────────────────────────────────────

def load_model():
    from FlagEmbedding import BGEM3FlagModel
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading BGE-M3 on {device}...")
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=(device == "cuda"))
    print("Model loaded.")
    return model


def embed_batch(model, texts):
    """Embed with max_length=512 to match query-time embedding window."""
    out = model.encode(texts, return_dense=True, return_sparse=True, max_length=512)
    dense_vecs = out["dense_vecs"]
    sparse_vecs = out["lexical_weights"]
    dense_list, sparse_list = [], []
    for i in range(len(texts)):
        d = dense_vecs[i]
        dense_list.append(d.tolist() if hasattr(d, "tolist") else list(d))
        s = sparse_vecs[i]
        indices = [int(k) for k in s.keys()]
        values = [float(v) for v in s.values()]
        sparse_list.append((indices, values))
    return dense_list, sparse_list


def setup_qdrant():
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams
    client = QdrantClient(url=QDRANT_URL, timeout=120)

    # Check if collection exists — only recreate if user confirms
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION in collections:
        info = client.get_collection(COLLECTION)
        count = info.points_count
        print(f"Collection '{COLLECTION}' exists with {count:,} points.")
        resp = input(f"Delete and recreate? (yes/no): ").strip().lower()
        if resp != "yes":
            print("Aborting. Use existing collection or delete manually.")
            sys.exit(0)
        client.delete_collection(COLLECTION)
        print(f"Deleted old '{COLLECTION}'.")

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams())},
    )
    print(f"Created '{COLLECTION}' collection.")
    return client


def catalog_to_text(api):
    title = api.get("title", "")
    desc = api.get("description", "")
    fields = api.get("fields", [])
    field_str = ", ".join(fields[:10]) if fields else ""
    text = f"{title}. {desc}"
    if field_str:
        text += f" Fields: {field_str}"
    return text[:512]


def spec_to_text(spec):
    name = spec.get("name", "")
    desc = spec.get("description", "")
    examples = spec.get("examples", [])
    text = f"{name}: {desc}"
    if examples:
        text += f" Examples: {'; '.join(examples[:3])}"
    return text[:512]


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    from qdrant_client.models import PointStruct, SparseVector

    # Load catalog (supports .gz and .json)
    if not os.path.exists(CATALOG_FILE):
        # Try alternate extension
        alt = CATALOG_FILE.replace(".json.gz", ".json") if CATALOG_FILE.endswith(".gz") else CATALOG_FILE + ".gz"
        if os.path.exists(alt):
            print(f"Found {alt} instead.")
            catalog_path = alt
        else:
            print(f"ERROR: {CATALOG_FILE} not found. Upload it to Colab first.")
            sys.exit(1)
    else:
        catalog_path = CATALOG_FILE

    print(f"Loading catalog from {catalog_path}...")
    if catalog_path.endswith(".gz"):
        with gzip.open(catalog_path, "rt", encoding="utf-8") as f:
            catalog = json.load(f)
    else:
        with open(catalog_path) as f:
            catalog = json.load(f)
    print(f"Loaded {len(catalog):,} APIs from data.gov.in")

    # Build entries: (id, text, payload)
    entries = []
    for i, api in enumerate(catalog):
        text = catalog_to_text(api)
        payload = {
            "api_id": api["id"],
            "title": api["title"],
            "description": api.get("description", ""),
            "source": "data.gov.in",
            "org_type": api.get("org_type", ""),
            "fields": api.get("fields", [])[:10],
            "updated": api.get("updated", ""),
        }
        entries.append((i, text, payload))

    # Custom tool specs
    offset = len(catalog)
    for j, spec in enumerate(CUSTOM_SPECS):
        text = spec_to_text(spec)
        payload = {
            "tool_name": spec["name"],
            "title": spec["name"],
            "description": spec["description"],
            "source": spec.get("source", "custom"),
            "domain": spec.get("domain", ""),
            "endpoint": spec.get("endpoint", ""),
            "examples": spec.get("examples", []),
        }
        entries.append((offset + j, text, payload))

    total = len(entries)
    print(f"\nTotal entries to ingest: {total:,}")
    print(f"  - data.gov.in catalog: {len(catalog):,}")
    print(f"  - Custom tool specs: {len(CUSTOM_SPECS)}")
    print(f"  - Batch size: {BATCH_SIZE}")
    print(f"  - Est. time (T4): ~{total / BATCH_SIZE * 3 / 60:.0f} min")
    print(f"  - Est. time (A100): ~{total / BATCH_SIZE * 1 / 60:.0f} min\n")

    # Load model
    model = load_model()

    # Setup Qdrant
    client = setup_qdrant()

    # Ingest
    start = time.time()
    uploaded = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = entries[batch_start:batch_start + BATCH_SIZE]
        texts = [e[1] for e in batch]

        dense_list, sparse_list = embed_batch(model, texts)

        points = []
        for k, (idx, text, payload) in enumerate(batch):
            indices, values = sparse_list[k]
            points.append(PointStruct(
                id=idx,
                vector={"dense": dense_list[k], "sparse": SparseVector(indices=indices, values=values)},
                payload=payload,
            ))

        client.upsert(collection_name=COLLECTION, points=points)
        uploaded += len(points)

        elapsed = time.time() - start
        rate = uploaded / elapsed
        eta = (total - uploaded) / rate if rate > 0 else 0
        pct = uploaded / total * 100
        print(f"  [{uploaded:>7,}/{total:,}] {pct:5.1f}% | {rate:.0f} APIs/s | ETA: {eta/60:.1f} min")

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"DONE! {uploaded:,} APIs indexed in {elapsed:.0f}s ({uploaded/elapsed:.0f} APIs/s)")
    print(f"Collection: '{COLLECTION}' on {QDRANT_URL}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
