# Jantar — Setup Guide

Complete instructions to get the project running from scratch.

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.13+ | Runtime |
| NVIDIA GPU | 4GB+ VRAM | BGE-M3 embeddings + reranker (CUDA) |
| Docker | Any | Qdrant vector database |
| Sarvam AI key | — | LLM + translation ([sarvam.ai](https://sarvam.ai)) |

## Step 1: Clone and Configure

```bash
git clone https://github.com/YOUR_USERNAME/jantar.git
cd jantar

# Copy environment template
cp .env.example .env
```

Edit `.env` with your values:

```env
SARVAM_API_KEY=sk_your_key_here      # Required — get from https://sarvam.ai
QDRANT_URL=http://localhost:6333       # Or your remote Qdrant instance
DATA_GOV_API_KEY=                      # Optional — register free at https://data.gov.in
API_KEY=your-server-auth-key           # Any string — protects the REST API
```

## Step 2: Install Dependencies

```bash
# Install PyTorch with CUDA first (match your CUDA version)
pip install torch --index-url https://download.pytorch.org/whl/cu124

# Install project dependencies
pip install -r requirements.txt
```

## Step 3: Start Qdrant

```bash
docker compose up -d
```

Verify: `curl http://localhost:6333/healthz` → `ok`

## Step 4: Index Data

### 4a. Register custom tool specs (7 free APIs)

```bash
python scripts/register_tools.py
```

This embeds 7 tool specifications (Open-Meteo weather/AQI, India Post, Razorpay IFSC, Sarvam translate/STT) into Qdrant using BGE-M3.

### 4b. Ingest knowledge base (21 government scheme documents)

```bash
python scripts/ingest_docs.py
```

This embeds 82 sections from 21 government schemes (ration card, PM-KISAN, Ayushman Bharat, driving licence, passport, DigiLocker, etc.) with contextual retrieval prefixes and parent-child indexing.

### 4c. (Optional) Index full data.gov.in catalog — 137,355 APIs

The full catalog requires a GPU with 16GB+ VRAM (use Google Colab free tier with T4).

1. Decompress the catalog:
   ```bash
   gunzip -k data/catalog/data_gov_in_deduped.json.gz
   ```

2. Upload `data_gov_in_deduped.json` to Google Colab

3. Run `scripts/colab_ingest.py` in Colab (set `QDRANT_URL` to your Qdrant endpoint)

After this step, the tool RAG can route queries to **137,362 APIs** covering every sector of Indian government data.

## Step 5: Run

### CLI — Single query

```bash
python -m jantar "राशन कार्ड के लिए कौन से दस्तावेज़ चाहिए?"
```

### CLI — Interactive mode (with conversation memory)

```bash
python -m jantar
```

### REST API server

```bash
python -m jantar serve
```

Then query:
```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"text": "PM-KISAN eligibility check", "language": "auto"}'
```

API docs: `http://localhost:8000/docs`

## Step 6: Run Tests

```bash
python -m pytest tests/ -q
```

---

## Architecture Overview

```
User Query (any of 22 Indian languages)
    ↓
Sarvam AI → detect language + translate to English
    ↓
Classifier (LLM) → single_step | multi_step | tool_action | knowledge_query | hybrid
    ↓
┌─── multi_step ──→ Planner (Plan-and-Execute, max 5 steps)
│                        ↓ per step
├─── tool_action ──→ Tool RAG (BGE-M3 dense+sparse → RRF → reranker → threshold)
│                        ↓
│                    Adapter dispatch → Live API call (data.gov.in / Open-Meteo / India Post / IFSC)
│
├─── knowledge_query → Knowledge RAG (same pipeline → parent expansion → citations)
│
└─── hybrid ──────→ Both tool + knowledge, merge results
    ↓
Answer Generation (Sarvam-30b) → response in user's language + citations
    ↓
Conversation Memory (progressive summary buffer, last 4 turns full)
```

## RAG Pipeline Detail

This is NOT naive vector search. The pipeline implements state-of-the-art multi-stage retrieval:

| Stage | What it does | Model/Method |
|-------|-------------|--------------|
| 1. Encoding | Single forward pass → 1024-dim dense vector + learned sparse lexical weights | BAAI/bge-m3 (FlagEmbedding, CUDA fp16) |
| 2. Dense search | Top-50 by cosine similarity | Qdrant HNSW index |
| 3. Sparse search | Top-50 by lexical overlap | Qdrant sparse index (vocabulary 250,002) |
| 4. Fusion | Reciprocal Rank Fusion (k=60) merges both ranked lists | `1/(k + rank + 1)` formula |
| 5. Cross-encoder rerank | Re-scores fused top-50 with joint query-document attention | BAAI/bge-reranker-v2-m3 (568M params, CUDA fp16) |
| 6. Threshold gate | Rejects results below 0.05 score (prevents false positives at 137K scale) | — |
| 7. Parent expansion | Returns full parent document (not just matched chunk) for LLM context | Qdrant payload retrieval |
| 8. Citation extraction | Attaches source URL, section path, effective date to every knowledge answer | Structured metadata |

**Why this matters:** Dense vectors catch semantic intent ("documents for ration card" matches "NFSA required documents"). Sparse vectors catch exact terms ("GSTIN" matches "GSTIN"). RRF merges both strengths. The cross-encoder reranker then re-reads query+document jointly (not just vector distance) for precision scoring. This achieves 0.99 retrieval accuracy on exact matches and correctly discriminates across 137,362 tools.

## Data Files

| Path | Contents | Size |
|------|----------|------|
| `data/catalog/data_gov_in_deduped.json.gz` | 137,355 data.gov.in APIs (compressed) | 10 MB |
| `data/tool_specs/*.json` | 7 custom free API definitions | 28 KB |
| `data/seed/knowledge_base.json` | 21 government schemes (ingest source) | 36 KB |
| `data/knowledge_docs/*.json` | Same 21 docs as individual files (for browsing) | 36 KB |
| `data/sources.md` | Full documentation of all data sources and APIs | 5 KB |

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `Illegal header value b'Bearer '` | Empty `SARVAM_API_KEY` in `.env` | Set the key |
| `Connection refused` on Qdrant | Docker not running or wrong URL | `docker compose up -d` and check `QDRANT_URL` |
| First query takes 30-40s | BGE-M3 model loading into GPU (cached after) | Normal on cold start |
| Sarvam response takes 60s+ | Reasoning model (sarvam-30b) is slow | Expected behavior — it's a reasoning model |
| GPU OOM during ingest | 4GB GPU can't batch-embed 5000+ texts | Use Colab for bulk catalog; local GPU handles queries fine |

## What's Indexed (after full setup)

- **137,362 tool vectors** — 137,355 data.gov.in APIs + 7 custom free APIs
- **82 knowledge vectors** — 21 government scheme documents across 82 sections
- **Covers:** Agriculture, health, education, transport, finance, energy, water, crime, employment, census, elections, housing, environment, tourism, tax, food security, social welfare, rural development, science, minerals, women & child, commerce, industry, telecom, postal, banking
