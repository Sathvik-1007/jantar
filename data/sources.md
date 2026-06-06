# Jantar — Data Sources & APIs

## Live API Integrations (7 tools, 4 adapters)

| Tool | Provider | Auth | Endpoint |
|------|----------|------|----------|
| `data_gov_dynamic` | data.gov.in (137K+ government datasets) | Free API key | `api.data.gov.in/resource/{id}` |
| `open_meteo_weather` | Open-Meteo | None | `api.open-meteo.com/v1/forecast` |
| `open_meteo_air_quality` | Open-Meteo | None | `air-quality-api.open-meteo.com/v1/air-quality` |
| `open_meteo_historical_weather` | Open-Meteo | None | `archive-api.open-meteo.com/v1/archive` |
| `india_post_pincode` | India Post (Government) | None | `api.postalpincode.in/pincode/{pin}` |
| `razorpay_ifsc` | Razorpay (RBI data) | None | `ifsc.razorpay.com/{code}` |
| `sarvam_translate` | Sarvam AI | API key | `api.sarvam.ai/translate` |
| `sarvam_stt` | Sarvam AI | API key | `api.sarvam.ai/speech-to-text` |

Note: Open-Meteo proxies what IMD would provide (no free IMD API exists).
Razorpay IFSC wraps RBI's public branch data (no free direct RBI API exists).

## data.gov.in Catalog

The full catalog (`data/catalog/data_gov_in_deduped.json.gz`, 137,355 unique APIs, 10MB compressed) is indexed
into Qdrant via the Colab ingest script. Covers all government sectors:

- Agriculture & Farmer Welfare
- Health & Family Welfare
- Education & Literacy
- Commerce & Industry
- Finance & Banking
- Labour & Employment
- Rural Development
- Housing & Urban Affairs
- Environment & Forests
- Science & Technology
- Transport & Highways
- Water Resources
- Energy & Power
- Crime & Police (NCRB)
- Women & Child Development
- Social Justice
- Tourism
- Food & Public Distribution
- Census & Demographics
- Elections
- Telecom
- Mining & Minerals

## Knowledge Base (21 documents, 82 sections)

| Document | Sections | Source |
|----------|----------|--------|
| National Food Security Act (NFSA) - Ration Card | 5 | nfsa.gov.in |
| PM-KISAN Samman Nidhi Yojana | 4 | pmkisan.gov.in |
| Ayushman Bharat PM-JAY | 4 | pmjay.gov.in |
| Driving Licence - Parivahan/Sarathi | 5 | parivahan.gov.in |
| Indian Passport - Passport Seva | 4 | passportindia.gov.in |
| EPFO - Provident Fund & Pension | 4 | epfindia.gov.in |
| DigiLocker - Digital Document Wallet | 4 | digilocker.gov.in |
| Income Tax - e-Filing | 4 | incometax.gov.in |
| Voter ID (EPIC) - Election Commission | 3 | eci.gov.in |
| PMMY - Pradhan Mantri MUDRA Yojana | 3 | mudra.org.in |
| National Scholarship Portal (NSP) | 3 | scholarships.gov.in |
| Aadhaar - UIDAI | 4 | uidai.gov.in |
| UPI - Unified Payments Interface | 3 | npci.org.in |
| PM Awas Yojana (PMAY) | 4 | pmaymis.gov.in |
| MGNREGA | 4 | nrega.nic.in |
| Sukanya Samriddhi Yojana (SSY) | 3 | indiapost.gov.in |
| Soil Health Card Scheme | 3 | soilhealth.dac.gov.in |
| UMANG | 3 | umang.gov.in |
| PM Fasal Bima Yojana (PMFBY) | 4 | pmfby.gov.in |
| e-Shram | 3 | eshram.gov.in |
| data.gov.in | 3 | data.gov.in |

## Future Integrations (require registration/empanelment)

| API | Provider | Blocker |
|-----|----------|---------|
| API Setu (DL/RC/PAN verification) | NIC/MeitY | Requires partner onboarding at partners.apisetu.gov.in |
| Bhashini (NLP/translation) | MeitY | Free for PoC, production requires paid tier |
| ABDM (health ID/records) | NHA | Requires sandbox registration + approval |
| Aadhaar (e-KYC/auth) | UIDAI | AUA/KUA empanelment + infra audit |
| UPI (payments) | NPCI | PSP/bank sponsorship + certification |
| GSTN (tax filing) | NIC | Requires licensed GSP |
| DigiLocker (document pull) | MeitY | Requester partner agreement |
| eCourts | NIC | Case data API not public |
| Land records | State govts | No unified API, state-by-state |

## Market Research References

- data.gov.in catalog: 285,000+ APIs (verified via API pagination, Jun 2026)
- Sarvam AI: 22 Indian languages, OpenAI-compatible API
- BGE-M3: MTEB benchmark leader for multilingual retrieval (1024-dim dense + learned sparse)
- BGE-reranker-v2-m3: 568M params, multilingual cross-encoder
- Contextual Retrieval (Anthropic): -67% retrieval failures (verified from paper)
- DSPy GEPA (ICLR 2026 oral): +10-12% prompt optimization over MIPROv2
