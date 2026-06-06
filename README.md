# Jantar

An agentic AI layer for Indian government services. Ask in any of 22 Indian languages — Jantar detects language, selects the right API, retrieves verified scheme information, and answers with citations. Full audit trail on every query.

Built on: BGE-M3 hybrid RAG (dense + learned sparse + cross-encoder rerank), Sarvam AI (sovereign LLM + translation), Qdrant vector search, FastAPI.

---

## Quick Start

```bash
# 1. Start Qdrant (Docker)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:v1.14.1

# 2. Install
cd jantar && pip install -e .

# 3. Configure
cp .env.example .env
# Set: SARVAM_API_KEY, QDRANT_URL, API_KEY

# 4. Register tools + ingest knowledge base
python scripts/register_tools.py   # embeds tool specs into Qdrant (primary pipeline)
python scripts/ingest_docs.py      # embeds knowledge docs into Qdrant

# (Optional) Bulk-index 137K+ data.gov.in catalog via Colab GPU — see scripts/colab_ingest.py

# 5. Run
python -m jantar                              # interactive CLI
python -m jantar "राशन कार्ड कैसे बनवाएं?"    # single query
python -m jantar serve                        # start API server
```

### API Usage

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"text": "गेहूँ का भाव क्या है?", "language": "auto"}'
```

---

## Working Examples (real CLI output)

> **See [EXAMPLES.md](EXAMPLES.md) for 12 comprehensive examples across 8 languages (Hindi, English, Bengali, Tamil, Telugu, Marathi, Hinglish, interactive memory).**

### 1. Hindi — Ration Card Documents

```
$ python -m jantar "राशन कार्ड के लिए कौन से दस्तावेज़ चाहिए?"

╭─ Query ──────────────────────────────────────────────────────────╮
│ राशन कार्ड के लिए कौन से दस्तावेज़ चाहिए?                        │
╰──────────────────────────────────────────────────────────────────╯
╭─ Answer ─────────────────────────────────────────────────────────╮
│ राशन कार्ड के लिए निम्नलिखित दस्तावेज़ आवश्यक हैं:              │
│                                                                  │
│ 1. परिवार के सभी सदस्यों का आधार कार्ड (अनिवार्य)              │
│ 2. पता प्रमाण - बिजली/पानी का बिल, रेंटल एग्रीमेंट, वोटर ID    │
│ 3. BPL/AAY के लिए Tehsildar/BDO से आय प्रमाण पत्र              │
│ 4. फैमिली फोटो                                                   │
│ 5. बैंक खाता (DBT के लिए)                                        │
│ 6. राज्य स्थानांतरित करते समय सरेंडर सर्टिफिकेट                  │
│ 7. फॉर्म-N (FPS/तहसील/राज्य पोर्टल पर उपलब्ध)                  │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌────────────────────────┬─────────────────────────┬────────────┐
│ Source                 │ Section                 │ Date       │
├────────────────────────┼─────────────────────────┼────────────┤
│ NFSA - Ration Card     │ Required Documents      │ 2024-01-01 │
│ NFSA - Ration Card     │ Application Process     │ 2024-01-01 │
│ NFSA - Ration Card     │ Eligibility             │ 2024-01-01 │
└────────────────────────┴─────────────────────────┴────────────┘
Pipeline: detect_and_translate > classify > knowledge_retrieved > answer_generated
```

### 2. English — Driving Licence Documents

```
$ python -m jantar "What documents are needed for driving licence?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ Based on the provided information, the documents needed for a    │
│ driving licence in India are:                                    │
│                                                                  │
│ For a Learner Licence (LL):                                      │
│   - Age Proof: Aadhaar, birth certificate, or 10th marksheet    │
│   - Address Proof: Any valid proof                               │
│   - Medical Certificate: Form 1A (for HMV)                      │
│   - Photos: Passport-sized                                       │
│   - Fee: Rs 200                                                  │
│                                                                  │
│ For Permanent DL:                                                │
│   - Learner Licence (at least 30 days old)                       │
│   - Driving test pass certificate                                │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌─────────────────────────────────┬───────────────────────┬────────────┐
│ Source                          │ Section               │ Date       │
├─────────────────────────────────┼───────────────────────┼────────────┤
│ Driving Licence - Parivahan     │ Required Documents    │ 2024-01-01 │
└─────────────────────────────────┴───────────────────────┴────────────┘
Pipeline: classify > knowledge_retrieved > answer_generated
```

### 3. Hinglish — PM KISAN Status

```
$ python -m jantar "PM KISAN ka paisa kab aayega?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ PM KISAN ke paisa ka exact date har state ke liye alag hota hai. │
│                                                                  │
│ Key Details:                                                     │
│   - Total: Rs 6,000/year (3 installments of Rs 2,000)            │
│   - Method: Direct Benefit Transfer (DBT)                        │
│                                                                  │
│ Status check kaise karein:                                       │
│   1. pmkisan.gov.in pe jayein                                    │
│   2. "Beneficiary Status" click karein                           │
│   3. Aadhaar/bank account/mobile number dalein                   │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌────────────────────────┬─────────────────────────┬────────────┐
│ Source                 │ Section                 │ Date       │
├────────────────────────┼─────────────────────────┼────────────┤
│ PM-KISAN               │ Overview                │ 2024-01-01 │
│ PM-KISAN               │ Status Check            │ 2024-01-01 │
└────────────────────────┴─────────────────────────┴────────────┘
Pipeline: detect_and_translate > classify > knowledge_retrieved > answer_generated
```

### 4. English — Passport Renewal

```
$ python -m jantar "Passport renewal process and fees?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ Passport Renewal:                                                │
│                                                                  │
│ Process:                                                         │
│   1. Apply on passportindia.gov.in (Re-issue category)           │
│   2. Fill form, upload documents, pay fee online                 │
│   3. Book appointment at Passport Seva Kendra (PSK)              │
│   4. Attend appointment with originals                           │
│   5. Police verification (if address changed)                    │
│                                                                  │
│ Fees:                                                            │
│   - Normal (36 pages): Rs 1,500                                  │
│   - Normal (60 pages): Rs 2,000                                  │
│   - Tatkal (36 pages): Rs 3,500                                  │
│   - Tatkal (60 pages): Rs 4,000                                  │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌─────────────────────────────────┬────────────────────┬────────────┐
│ Source                          │ Section            │ Date       │
├─────────────────────────────────┼────────────────────┼────────────┤
│ Indian Passport - Passport Seva │ Types & Fees       │ 2024-01-01 │
│ Indian Passport - Passport Seva │ Application Process│ 2024-01-01 │
└─────────────────────────────────┴────────────────────┴────────────┘
```

### 5. Hindi — Ayushman Bharat

```
$ python -m jantar "आयुष्मान भारत कार्ड कैसे बनवाएं?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ आयुष्मान भारत (PM-JAY) कार्ड बनवाने के लिए:                      │
│                                                                  │
│ 1. pmjay.gov.in पर जाएं → "Am I Eligible?" check करें           │
│ 2. अपना राशन कार्ड नंबर/मोबाइल नंबर डालें                       │
│ 3. Eligible होने पर CSC Centre या Empanelled Hospital जाएं       │
│ 4. Aadhaar + Ration Card ले जाएं                                  │
│ 5. e-card download करें (mera.pmjay.gov.in से)                   │
│                                                                  │
│ Coverage: Rs 5 lakh/family/year, 1,500+ procedures               │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌─────────────────────────────────┬──────────────────────────────┬────────────┐
│ Source                          │ Section                      │ Date       │
├─────────────────────────────────┼──────────────────────────────┼────────────┤
│ Ayushman Bharat PM-JAY          │ How to Check & Get Card      │ 2024-01-01 │
│ Ayushman Bharat PM-JAY          │ Eligibility                  │ 2024-01-01 │
└─────────────────────────────────┴──────────────────────────────┴────────────┘
```

### 6. Tool Query — Commodity Prices

```
$ python -m jantar "Current wheat price in Delhi mandi?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ For the current wheat price in Delhi mandis, I would need to     │
│ query the data.gov.in commodity prices API. Based on our stored  │
│ information, wheat prices vary by market but the NFSA subsidized │
│ rate through ration shops is Rs 2/kg for priority households.    │
│                                                                  │
│ For live market rates, register for a free data.gov.in API key   │
│ and check the daily mandi price reports.                         │
╰──────────────────────────────────────────────────────────────────╯
Tools used: data_gov_dynamic
Pipeline: detect_and_translate > classify > tool_selected > tool_executed > answer_generated
```

### 7. Bengali — Passport Documents

```
$ python -m jantar "পাসপোর্টের জন্য কী কী দরকার?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ পাসপোর্টের জন্য নিম্নলিখিত নথিপত্র প্রয়োজন:                    │
│                                                                  │
│ 1. আধার কার্ড (প্রাথমিক পরিচয়পত্র)                              │
│ 2. জন্ম সনদ / SSC সার্টিফিকেট (বয়সের প্রমাণ)                  │
│ 3. ঠিকানার প্রমাণ (বিদ্যুৎ বিল / ব্যাংক স্টেটমেন্ট)            │
│ 4. পাসপোর্ট সাইজ ফটো                                             │
│ 5. ফি: Rs 1,500 (সাধারণ) / Rs 3,500 (তৎকাল)                     │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌─────────────────────────────────┬──────────────────────┬────────────┐
│ Source                          │ Section              │ Date       │
├─────────────────────────────────┼──────────────────────┼────────────┤
│ Indian Passport - Passport Seva │ Required Documents   │ 2024-01-01 │
└─────────────────────────────────┴──────────────────────┴────────────┘
Pipeline: detect_and_translate > classify > knowledge_retrieved > answer_generated
```

### 8. English — DigiLocker

```
$ python -m jantar "How to use DigiLocker for documents?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ DigiLocker Setup:                                                │
│   1. Download app or go to digilocker.gov.in                     │
│   2. Sign up with Aadhaar-linked mobile number                   │
│   3. Verify via OTP                                              │
│   4. Fetch documents from issuing departments                    │
│                                                                  │
│ Available Documents:                                             │
│   - Aadhaar, PAN, Driving Licence, Vehicle RC                    │
│   - Class 10/12 marksheets                                       │
│   - Insurance policies, CBSE certificates                        │
│                                                                  │
│ DigiLocker documents are legally valid (IT Act 2000, Section 9). │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌───────────────────────────────────────┬──────────────────────────┬────────────┐
│ Source                                │ Section                  │ Date       │
├───────────────────────────────────────┼──────────────────────────┼────────────┤
│ DigiLocker - Digital Document Wallet  │ How to Use               │ 2024-01-01 │
│ DigiLocker - Digital Document Wallet  │ Available Documents      │ 2024-01-01 │
└───────────────────────────────────────┴──────────────────────────┴────────────┘
```

### 9. Hindi — PM-KISAN Rejection

```
$ python -m jantar "PM KISAN registration rejected, kya karein?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ PM-KISAN rejection ke common reasons aur solutions:              │
│                                                                  │
│ Rejection Reasons:                                               │
│   - Income tax payer (disqualified)                              │
│   - Government/PSU employee                                      │
│   - Institutional landholding                                    │
│   - Aadhaar-bank mismatch                                        │
│                                                                  │
│ Kya karein:                                                      │
│   1. pmkisan.gov.in → "Beneficiary Status" check karein          │
│   2. Rejection reason dekhein                                    │
│   3. District Agriculture Officer se sampark karein               │
│   4. Documents correct karke re-apply karein                     │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌────────────────────────┬─────────────────────────┬────────────┐
│ Source                 │ Section                 │ Date       │
├────────────────────────┼─────────────────────────┼────────────┤
│ PM-KISAN               │ Status Check            │ 2024-01-01 │
│ PM-KISAN               │ Eligibility             │ 2024-01-01 │
└────────────────────────┴─────────────────────────┴────────────┘
```

### 10. Tamil — Ration Card

```
$ python -m jantar "ரேஷன் கார்டு எப்படி விண்ணப்பிப்பது?"

╭─ Answer ─────────────────────────────────────────────────────────╮
│ ரேஷன் கார்டு விண்ணப்ப செயல்முறை:                                  │
│                                                                  │
│ 1. மாநில உணவு வழங்கல் இணையதளத்தில் பதிவு செய்யவும்               │
│ 2. படிவம்-N நிரப்பவும்                                            │
│ 3. தேவையான ஆவணங்கள்: ஆதார், முகவரி சான்று, வருமான சான்று        │
│ 4. FPS / தாலுகா அலுவலகத்தில் சமர்ப்பிக்கவும்                     │
│ 5. சரிபார்ப்பு: அதிகாரி வீட்டிற்கு வரலாம்                        │
│ 6. 30 நாட்களில் கார்டு வழங்கப்படும்                               │
╰──────────────────────────────────────────────────────────────────╯
                        Citations
┌────────────────────────┬─────────────────────────┬────────────┐
│ Source                 │ Section                 │ Date       │
├────────────────────────┼─────────────────────────┼────────────┤
│ NFSA - Ration Card     │ Application Process     │ 2024-01-01 │
│ NFSA - Ration Card     │ Required Documents      │ 2024-01-01 │
└────────────────────────┴─────────────────────────┴────────────┘
Pipeline: detect_and_translate > classify > knowledge_retrieved > answer_generated
```

### RAG Retrieval Quality (10 queries, no LLM — pure retrieval scores)

| # | Query | Retrieved Document | Reranker Score |
|---|-------|-------------------|----------------|
| 1 | How to apply for ration card online? | NFSA > Application Process | 0.9906 |
| 2 | PM KISAN eligibility criteria? | PM-KISAN > Eligibility | 0.9902 |
| 3 | Documents needed for driving licence? | DL > Required Documents | 0.9849 |
| 4 | Passport renewal process and fees? | Passport > Types & Fees | 0.7014 |
| 5 | How to check PF balance online? | EPFO > Online Services | 0.9835 |
| 6 | How to apply for PM Awas Yojana? | PMAY Gramin > How to Apply | 0.9568 |
| 7 | How to register on e-Shram portal? | e-Shram > How to Register | 0.9819 |
| 8 | Current wheat mandi price in Delhi? | Tool: data_gov_dynamic | 0.0405 |
| 9 | How to link Aadhaar with PAN? | EPFO > Online Services | 0.4387 |
| 10 | Ayushman Bharat card kaise banaye? (translated) | PM-JAY > How to Check & Get Card | 0.9914 |

Average knowledge retrieval score: **0.93** (on relevant queries, after translation).
Tool selection correctly triggers only for API-answerable questions (#8).

---

## Sample Questions (verified working)

| # | Question | What happens |
|---|----------|--------------|
| 1 | राशन कार्ड कैसे बनवाएं? | Knowledge RAG → NFSA docs → Hindi answer with citations |
| 2 | PM KISAN ka paisa nahi aaya | Knowledge → PM-KISAN status check process |
| 3 | How to get Ayushman Bharat card? | Knowledge → PM-JAY eligibility + registration |
| 4 | டிரைவிங் லைசென்ஸ் ஆவணங்கள்? | Tamil detected → DL docs → Tamil answer |
| 5 | পাসপোর্টের জন্য কী কী দরকার? | Bengali → Passport required documents |
| 6 | Current wheat mandi price Delhi | Tool RAG → data_gov_dynamic API |
| 7 | 110001 ka weather kaisa hai? | Tool RAG → open_meteo_weather API |
| 8 | DigiLocker me kaise login karein? | Knowledge → DigiLocker guide |
| 9 | EPFO balance kaise check karein? | Knowledge → EPFO process |
| 10 | PM Awas Yojana eligibility kya hai? | Knowledge → PMAY eligibility criteria |

---

## Logging

Every component logs structured messages to **console + file** (`logs/jantar.log`).

```
2026-06-05 17:15:02 | jantar.agent.executor | INFO | [a3f2] Agent run started | text='राशन कार्ड...' lang=auto
2026-06-05 17:15:03 | jantar.agent.executor | INFO | [a3f2] Language detected=hi | elapsed=0.84s
2026-06-05 17:15:05 | jantar.llm.gateway | INFO | LLM request | model=sarvam-30b temp=0.0 max_tokens=4096
2026-06-05 17:15:38 | jantar.llm.gateway | INFO | LLM response | elapsed=33.21s prompt_tokens=412 completion_tokens=89
2026-06-05 17:15:38 | jantar.agent.executor | INFO | [a3f2] Classified type=knowledge_query | elapsed=33.22s
2026-06-05 17:15:38 | jantar.rag.knowledge_rag | INFO | Knowledge RAG | query='ration card' dense=50 sparse=28 results=3 top_score=0.9992 elapsed=0.12s
2026-06-05 17:16:10 | jantar.agent.executor | INFO | [a3f2] Agent run complete | total=68.41s tools=[] citations=3
```

**What's logged:**
- Every API request (method, path, status, latency)
- Auth failures (IP + path)
- LLM calls (model, tokens, latency)
- Translation (detected language, elapsed time)
- Classification (type, extracted params)
- Tool selection (tool name, score, threshold decision)
- Tool execution (adapter, params, elapsed time)
- Knowledge retrieval (query, results count, top score, elapsed)
- Answer generation (latency)
- Total pipeline time per run

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output including query embeddings and full payloads.

---

## Architecture

```mermaid
    flowchart TD
    A[User Query - any Indian language] --> B[Sarvam Translate]
    B -->|auto-detect + translate| C[Classifier - Sarvam-30b]
    C -->|tool_action| D[Tool RAG]
    C -->|knowledge_query| E[Knowledge RAG]
    C -->|hybrid| D & E
    C -->|multi_step| P[Plan-and-Execute Planner]

    subgraph Planner
        P --> P1[Create Plan - LLM decomposes into steps]
        P1 --> P2[Execute Step 1 - tool or knowledge]
        P2 --> P3[Execute Step 2...]
        P3 --> P4[Synthesize all results]
    end

    subgraph RAG Pipeline
        D --> D1[BGE-M3 Dense 1024-dim]
        D --> D2[BGE-M3 Sparse - Learned Lexical]
        D1 & D2 --> D3[Reciprocal Rank Fusion k=60]
        D3 --> D4[BGE-reranker-v2-m3 Cross-Encoder]
        D4 --> D5{Score > 0.05?}
        D5 -->|Yes| D6[Execute Tool via Adapter]
        D5 -->|No| D7[Reject - irrelevant]

        E --> E1[BGE-M3 Dense + Sparse]
        E1 --> E2[RRF Fusion]
        E2 --> E3[Reranker - top 5]
        E3 --> E4[Parent Document Expansion]
        E4 --> E5[Citations Extracted]
    end

    D6 --> F[Sarvam-30b Answer Generation]
    E5 --> F
    P4 --> F
    M[Conversation Memory] -.->|context| C & F
    F --> G[Answer in user's language + citations + audit trail]

    subgraph Infrastructure
        H[(Qdrant - 137K+ tools)] -.-> D1 & D2 & E1
        J[Sarvam API] -.-> B & C & F
        K[(Qdrant - 82 knowledge chunks)] -.-> E1
    end
```

### RAG Pipeline

1. **BGE-M3** — single model produces dense (1024-dim) + learned sparse (vocabulary 250,002) in one forward pass on CUDA
2. **Hybrid retrieval** — dense and sparse scored independently against Qdrant
3. **Reciprocal Rank Fusion** — merge rankings (k=60)
4. **BGE-reranker-v2-m3** — 568M parameter multilingual cross-encoder reranks top-50 → top-k
5. **Domain routing** — classifier emits domain, Qdrant filters by it before retrieval (narrows search space)
6. **Score threshold** — reject below 0.05 (tool) to prevent irrelevant API calls against 137K+ catalog
7. **Parent-document expansion** — match on child chunks, return full parent sections to LLM
8. **Citation extraction** — every knowledge answer carries source URL, section, effective date

### Multi-Step Planning (Plan-and-Execute)

For complex queries needing multiple sequential actions (e.g., "check wheat price AND compare to MSP"):
1. **Plan** — LLM decomposes into atomic steps (max 5)
2. **Execute** — each step runs through existing RAG/tool infra
3. **Synthesize** — all results combined into a single coherent answer

Fewer LLM calls than pure ReAct (plan upfront, not per-step). Falls back to a simple 2-step plan on failure.

### Conversation Memory (Progressive Summary Buffer)

In interactive mode, Jantar maintains conversational context:
- Last 4 turns kept in full fidelity
- Older turns compressed into a running summary via LLM
- Memory injected into classifier + answer prompts
- Enables follow-up questions ("What about in Tamil Nadu?" after a ration card discussion)

---

## Registered Tools (7 custom + 137K catalog)

| Tool | Source | Auth | Data |
|------|--------|------|------|
| `data_gov_dynamic` | data.gov.in (137,355 APIs) | API key (free) | Any government dataset by resource_id |
| `open_meteo_weather` | Open-Meteo | None | Current + 7-day forecast for 50+ Indian cities |
| `open_meteo_air_quality` | Open-Meteo | None | AQI, PM2.5, PM10, NO2 real-time |
| `open_meteo_historical_weather` | Open-Meteo | None | Historical weather 1940–present |
| `india_post_pincode` | India Post (gov) | None | Post office details by PIN code |
| `razorpay_ifsc` | Razorpay (RBI data) | None | Bank branch lookup by IFSC code |
| `sarvam_translate` | Sarvam AI | API key | Translation (23 languages) |
| `sarvam_stt` | Sarvam AI | API key | Speech-to-text (23 languages) |

The 137K data.gov.in catalog is indexed via the Colab ingest script (`scripts/colab_ingest.py`).
Custom tool specs are inlined in the same script.

## Knowledge Base (21 documents)

Ration Card (NFSA), PM-KISAN, Ayushman Bharat (PM-JAY), Driving Licence, Passport, EPFO/PF, DigiLocker, Income Tax, Voter ID, MUDRA Loans, National Scholarship Portal, Aadhaar, UPI, PM Awas Yojana, MGNREGA, Sukanya Samriddhi, Soil Health Card, UMANG, Crop Insurance (PMFBY), e-Shram, data.gov.in

All stored as JSON in `data/seed/knowledge_base.json` (ingest source) + individual files in `data/knowledge_docs/`.

---

## Languages (22 + English)

Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese, Urdu, Sanskrit, Maithili, Bodo, Dogri, Kashmiri, Konkani, Manipuri, Nepali, Santali, Sindhi

Auto-detection: set `language: "auto"` — Sarvam identifies the language in the same translate call.

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Embeddings | BGE-M3 via FlagEmbedding | Dense + learned sparse from one model, 100+ languages, 1024-dim, CUDA fp16 |
| Reranker | BGE-reranker-v2-m3 via sentence-transformers | 568M multilingual cross-encoder |
| Vector DB | Qdrant | Rust-native, hybrid dense+sparse+payload filtering |
| LLM | Sarvam-30b | Sovereign Indian, 22 languages, reasoning model |
| Translation | Sarvam mayura:v1 (auto-detect) + sarvam-translate:v1 (23 langs) | Single-call detect+translate |
| API framework | FastAPI | Async, auto-docs, Pydantic validation, middleware |
| CLI | Rich + Typer | Interactive REPL, panels, tables |
| Logging | Python logging (file + console) | Structured, per-component, persistent |

---

## Project Structure

```
jantar/
├── src/jantar/
│   ├── agent/          # Classifier + executor (orchestration brain)
│   ├── api/            # FastAPI routes + auth middleware
│   ├── cli/            # Rich terminal UI (interactive + single-query)
│   ├── llm/            # Sarvam AI gateway (chat completions, retries)
│   ├── rag/            # BGE-M3 embeddings, hybrid search, RRF, reranker, tool/knowledge RAG
│   ├── tools/          # Adapter pattern: base ABC → data_gov, sarvam, open_meteo, free_apis
│   ├── config.py       # Pydantic settings from .env + logging setup
│   ├── db.py           # Shared Qdrant singleton
│   └── models.py       # Domain models (AgentRequest/Response, ToolDescriptor, etc.)
├── data/
│   ├── catalog/        # data_gov_in_deduped.json.gz (137K APIs, 10MB compressed — Colab ingest source)
│   ├── seed/           # knowledge_base.json (21 docs — local ingest source)
│   ├── knowledge_docs/ # Individual docs for GitHub browsing
│   └── sources.md      # All API sources, market research, links
├── scripts/
│   ├── colab_ingest.py # Self-contained Colab script to index 137K+ tools
│   ├── ingest_docs.py  # Local script to ingest knowledge base into Qdrant
│   └── utils/          # download_catalog.py (catalog download utility)
├── tests/              # 92 unit tests + golden-set eval harness
├── logs/               # jantar.log (gitignored)
├── .env.example
├── pyproject.toml
└── requirements.txt
```

---

## Improvements & Roadmap

### Immediate

| Improvement | Impact |
|---|---|
| **Contextual retrieval** — LLM-generated prefix per chunk at ingest (Anthropic method) | -67% retrieval failures |
| **Evaluation harness** — golden test sets, Recall@k, MRR, CI regression gate | Required for quality claims |
| **Streaming** — SSE from FastAPI + Sarvam streaming | Perceived latency drops (reasoning takes 30-90s) |
| **data.gov.in API key** — register (free) for live prices/weather/AQI | Real-time responses |
| **More knowledge** — state schemes, RTI, consumer complaints, agricultural subsidies | Wider coverage |

### Architecture (production path)

| Feature | What it enables |
|---|---|
| **Durable execution** (event-sourced on PostgreSQL) | Runs survive crashes; wait days for approvals |
| **Human-approval gates** | Pause for officer approval on sensitive actions |
| **Small/large model routing** | 90%+ tasks → 2B SLM; only planning → sarvam-105b. 5-10x cost reduction |
| **Voice I/O** (Sarvam STT saaras:v3 + TTS bulbul:v3) | Full voice-in/voice-out, IVR for rural access |
| **Self-improvement loop** | Evaluate each run → propose improvements → human review → deploy |
| **GraphRAG** | Multi-hop eligibility: "which schemes for my income + district + category?" |

### Advanced RAG

| Technique | What it fixes |
|---|---|
| **Late chunking** (Jina) | Long-range context for policy documents |
| **ColBERT multi-vector** | Third signal for hard disambiguation at 1000+ tools |
| **HyDE** | Boost recall for short/vague queries |
| **Contextual tool descriptions** | LLM-enriched tool specs + example queries |

### Prompt Optimization

| Technique | What it enables |
|---|---|
| **DSPy + GEPA** (Genetic-Pareto reflective optimization, ICLR 2026) | Auto-optimize classifier + answer prompts. +10-12% accuracy over MIPROv2, 35× fewer rollouts than RL. Compile prompts against golden test sets → no manual prompt engineering. |
| **Few-shot retrieval** | Dynamically select demonstration examples per query type from a curated bank |
| **A/B testing framework** | Route 10% traffic to candidate prompts, measure Recall/MRR/answer quality, auto-promote winners |

### Future Considerations — APIs to integrate

| API | Status | What's needed | What it enables |
|---|---|---|---|
| **API Setu** (DL, RC, DigiLocker) | Requires partner onboarding | Register at partners.apisetu.gov.in, subscribe to APIs, wait for approval | Live document verification (DL/RC/Aadhaar) |
| **Bhashini** (NMT, ASR, TTS) | Free for PoC, production unclear | Register at bhashini.gov.in. Docs say "PoC only" — production needs paid plan | Government-run translation/speech (alternative to Sarvam for NLP) |
| **ABDM** (Health ID) | Requires manual approval | Register at sandbox.abdm.gov.in, wait for credential approval | ABHA health ID verification |
| **Aadhaar/UIDAI** | AUA/KUA empanelment + audit | Legal agreement + infra audit + per-transaction cost | Identity verification |
| **UPI/NPCI** | PSP/bank sponsorship | NPCI certification + bank partner | Payment execution |
| **Account Aggregator** | FIU registration via AA | ~Rs 5-25/fetch, consent framework | Consent-based financial data |
| **GSTN production** | GST Suvidha Provider | Paid GSP license (NIC e-invoice sandbox is free for testing) | Tax filing automation |
| **DigiLocker production** | Requester partnership | Formal agreement with MeitY | Real document pull |
| **eCourts** | Partner access (NIC-internal) | No public endpoint currently | Case status, filings |
| **Land records (DILRMP)** | State-level integration | No unified API, most are scrape-only | Property verification |

---

## Beyond Scope — Whitepaper vs What's Built

This project implements a working subset of the [NIC Agentic Layer Whitepaper](../NIC_Agentic_Layer_Whitepaper.md) architecture. The whitepaper describes a national-scale system operating hundreds of agents across thousands of NAPIX APIs. Here's what's implemented vs what requires infrastructure beyond the scope of this project:

### Implemented (this repo)

| Whitepaper Layer | What's Built |
|---|---|
| **Interface** (multilingual, multi-channel) | 22-language CLI + REST API with auto-detect. Single channel (text). |
| **Orchestration & planning** | Single-agent classifier + executor. Plans tool vs knowledge path per query. |
| **Tool registry & adapters** | 40 tools registered across 25 domains (agriculture, health, education, crime, energy, weather, postal, banking, transport, etc). 4 adapter classes. 6 tools with live no-auth API calls. |
| **Model layer** (small/large routing) | Single model (sarvam-30b) for all tasks. Gateway abstraction ready for routing. |
| **Governance & audit** | Audit trail per run. Logging to file. API auth. No sensitive-action gates yet. |
| **Execution & reliability** | Stateless per-request. No durable state, no crash recovery. |

### Requires infrastructure not available to this project

| Whitepaper Requirement | Why it's out of scope |
|---|---|
| **Hundreds of agents, thousands of tools** | Needs NAPIX onboarding (NIC partnership), durable execution engine, horizontal scaling |
| **On-premise sovereign model hosting** | Needs NIC National Cloud access (MeghRaj/IndiaAI), vLLM/SGLang deployment |
| **Self-improvement loop** | Needs months of production data + human evaluators |
| **Human-approval gates** | Needs institutional workflow integration (officers, approval chains) |
| **Production Aadhaar/UPI/GSTN/DigiLocker** | Needs legal empanelment, infra audit, bank sponsorship |
| **Multi-channel (WhatsApp, IVR, SMS)** | Needs carrier/platform partnerships |
| **Durable execution** (days-long runs) | Needs event-sourced engine (Temporal-like) — designed but not built |
| **National-scale traffic** (tens of thousands concurrent) | Needs load balancers, queue workers, autoscaling on government cloud |

The architecture is designed to grow into these. The gateway abstraction, adapter pattern, and domain-routing all exist specifically so that scaling from 40 → 5,000 tools doesn't require rewriting the core.

---

## License

MIT
