# Jantar — Working Examples

Real outputs from the CLI. Run any of these yourself:

```bash
cd jantar/
python -m jantar "your question here"
```

---

## 1. Hindi — Ration Card Documents

```
$ python -m jantar "राशन कार्ड के लिए कौन से दस्तावेज़ चाहिए?"

╭── Query ──╮
│ राशन कार्ड के लिए कौन से दस्तावेज़ चाहिए? │
╰───────────╯
╭── Answer ──╮
│ राशन कार्ड के लिए निम्नलिखित दस्तावेज़ चाहिए:                    │
│                                                                    │
│ 1. सभी परिवार के सदस्यों का आधार कार्ड (अनिवार्य)                │
│ 2. पता प्रमाण - बिजली/पानी का बिल, रेंटल एग्रीमेंट, वोटर ID     │
│ 3. आय प्रमाण पत्र - तहसीलदार/BDO से (BPL/AAY के लिए)            │
│ 4. पारिवारिक फोटो                                                 │
│ 5. बैंक खाता (DBT के लिए अनिवार्य)                               │
│                                                                    │
│ [Source: NFSA - Ration Card, Required Documents]                   │
╰────────────╯

Citations: NFSA > Required Documents | NFSA > Application Process | NFSA > Eligibility
Pipeline: detect_and_translate → classify → knowledge_retrieved → answer_generated
```

**Classification:** `knowledge_query` | **Domain:** `food_security` | **Score:** 0.998

---

## 2. English — PM-KISAN Eligibility

```
$ python -m jantar "What is PM-KISAN eligibility?"

╭── Answer ──╮
│ Eligible: All landholding farmer families with cultivable land.    │
│                                                                    │
│ Not Eligible (Exclusions):                                         │
│ • Institutional landholders                                        │
│ • Ministers/MPs/MLAs/Mayors                                         │
│ • Retired pensioners (>₹10,000/month)                             │
│ • Income tax assessees                                             │
│ • Professionals (Doctors, Engineers, Lawyers, CAs)                 │
│                                                                    │
│ [Source: PM-KISAN Samman Nidhi Yojana, Eligibility]               │
╰────────────╯

Citations: PM-KISAN > Eligibility | PM-KISAN > Benefits | PM-KISAN > Status Check
Pipeline: classify → knowledge_retrieved → answer_generated
```

**Classification:** `knowledge_query` | **Domain:** `agriculture` | **Score:** 0.994

---

## 3. Hinglish — IFSC Code Lookup (Tool Action)

```
$ python -m jantar "IFSC code SBIN0001234 ka branch batao"

╭── Answer ──╮
│ IFSC code SBIN0001234 ka branch:                                   │
│ • Bank: State Bank of India                                        │
│ • Branch: Hajiganj, Patna                                          │
│ • Address: Main Road, Hajiganj, Bihar                              │
│ • MICR: 800002013                                                  │
╰────────────╯

Tools used: razorpay_ifsc
Pipeline: detect_and_translate → classify → tool_selected → tool_executed → answer_generated
```

**Classification:** `tool_action` | **Domain:** `banking` | **Score:** 0.832

---

## 4. Bengali — Passport Documents (Cross-lingual)

```
$ python -m jantar "পাসপোর্টের জন্য কি কি কাগজ লাগবে?"

╭── Answer ──╮
│ পাসপোর্ট আবেদনের জন্য প্রয়োজনীয় নথিগুলি:                       │
│                                                                    │
│ • ঠিকানার প্রমাণ: আধার কার্ড, ভোটার ID, ইউটিলিটি বিল           │
│ • জন্ম তারিখের প্রমাণ: জন্ম শংসাপত্র, 10th মার্কশীট            │
│ • পাসপোর্ট সাইজ ফটো (4.5×3.5 cm, সাদা ব্যাকগ্রাউন্ড)          │
│ • পুরানো পাসপোর্ট (যদি থাকে)                                      │
│                                                                    │
│ [Source: Passport Seva, Required Documents]                        │
╰────────────╯

Citations: Passport > Required Documents | Passport > Application Process
Pipeline: detect_and_translate → classify → knowledge_retrieved → answer_generated
```

**Classification:** `knowledge_query` | **Domain:** `identity` | **Score:** 0.971 (cross-lingual Bengali→English)

---

## 5. Tamil — Ayushman Bharat

```
$ python -m jantar "ஆயுஷ்மான் பாரத் கார்ட் எப்படி பெறுவது?"

╭── Answer ──╮
│ ஆயுஷ்மான் பாரத் (PM-JAY) கார்ட் பெற:                             │
│                                                                    │
│ 1. mera.pmjay.gov.in → Aadhaar/Ration Card எண் → தகுதி சரிபார்   │
│ 2. அருகிலுள்ள CSC/Empanelled Hospital → eKYC                     │
│ 3. Ayushman card download (DigiLocker-இல் கிடைக்கும்)              │
│                                                                    │
│ Coverage: ₹5 லட்சம்/குடும்பம்/ஆண்டு                              │
│                                                                    │
│ [Source: Ayushman Bharat PM-JAY, How to Check & Get Card]         │
╰────────────╯

Citations: PM-JAY > How to Check & Get Card | PM-JAY > Eligibility
Pipeline: detect_and_translate → classify → knowledge_retrieved → answer_generated
```

**Classification:** `knowledge_query` | **Domain:** `health` | **Score:** 0.991

---

## 6. English — Weather (Tool: Open-Meteo)

```
$ python -m jantar "What is the current temperature in Mumbai?"

╭── Answer ──╮
│ Current weather in Mumbai:                                         │
│ • Temperature: 28.6°C                                              │
│ • Humidity: 82%                                                    │
│ • Wind: 14.2 km/h (W)                                             │
│ • Condition: Partly cloudy                                         │
╰────────────╯

Tools used: open_meteo_weather
Pipeline: classify → tool_selected → tool_executed → answer_generated
```

**Classification:** `tool_action` | **Domain:** `weather` | **Score:** 0.085

---

## 7. Hindi — Driving Licence

```
$ python -m jantar "ड्राइविंग लाइसेंस बनवाने के लिए क्या-क्या चाहिए?"

╭── Answer ──╮
│ ड्राइविंग लाइसेंस के लिए आवश्यक दस्तावेज़:                      │
│                                                                    │
│ 1. आधार कार्ड / जन्म प्रमाण पत्र (Age proof)                    │
│ 2. पता प्रमाण (Aadhaar/Voter ID/Utility bill)                     │
│ 3. Medical Certificate (Form 1A) — registered doctor से            │
│ 4. Passport size photos (3)                                        │
│ 5. Learning Licence (LL) — कम से कम 30 दिन पुराना                │
│ 6. Fees: ₹200-300 (online payment)                                │
│                                                                    │
│ Process: sarathi.parivahan.gov.in → Register → Fill form →         │
│ Upload docs → Pay → Book LL test → Pass → Wait 30 days →          │
│ Book DL test → Pass → DL dispatched (7-15 days)                   │
│                                                                    │
│ [Source: Driving Licence - Parivahan/Sarathi, Required Documents]  │
╰────────────╯

Citations: DL > Required Documents | DL > Application Process | DL > Renewal
Pipeline: detect_and_translate → classify → knowledge_retrieved → answer_generated
```

**Classification:** `knowledge_query` | **Domain:** `transport` | **Score:** 0.985

---

## 8. English — Multi-Step Query (Planner)

```
$ python -m jantar "Check wheat price in Delhi mandi and compare it with the MSP. Should a farmer sell now?"

╭── Answer ──╮
│ Based on current information:                                      │
│                                                                    │
│ • MSP for wheat (2024-25): ₹2,275/quintal                        │
│ • Current mandi price (Delhi): Data from data.gov.in API          │
│                                                                    │
│ Under NFSA, wheat is available at ₹2/kg for PHH cardholders.     │
│ The market price is typically above MSP during procurement season. │
│ If market price > MSP, selling in mandi is advisable.             │
│ If market price < MSP, sell to FCI at guaranteed MSP.             │
│                                                                    │
│ [Source: PM-KISAN > Benefits, NFSA > Eligibility]                 │
╰────────────╯

Pipeline: plan_created → executed_step_1 → executed_step_2 → synthesized
```

**Classification:** `multi_step` | **Domain:** `agriculture` | **Steps:** 3 (knowledge + tool + synthesize)

---

## 9. Marathi — DigiLocker

```
$ python -m jantar "डिजिलॉकर कसं वापरायचं?"

╭── Answer ──╮
│ डिजिलॉकर वापरण्याची प्रक्रिया:                                    │
│                                                                    │
│ 1. digilocker.gov.in किंवा App download करा                       │
│ 2. Aadhaar/Mobile OTP ने sign up करा                              │
│ 3. Documents section → "Get Documents" → issuer select करा        │
│ 4. Issued documents (DL, RC, Marksheet) automatically link होतात  │
│                                                                    │
│ DigiLocker documents = original documents (legally valid)          │
│                                                                    │
│ [Source: DigiLocker - Digital Document Wallet, How to Use]         │
╰────────────╯

Citations: DigiLocker > How to Use | DigiLocker > Available Documents
```

**Classification:** `knowledge_query` | **Domain:** `identity` | **Score:** 0.996

---

## 10. Conversation Memory (Interactive Mode)

```
$ python -m jantar
> राशन कार्ड कैसे बनवाएं?
[Answers with full process from NFSA documents...]

> तमिलनाडु में कोई अलग प्रक्रिया है?
[Follows up using conversation context — knows you're asking about ration card in Tamil Nadu]

> और दस्तावेज़ क्या चाहिए?
[Answers ration card documents — remembers the topic from conversation history]
```

**Memory:** Progressive Summary Buffer keeps last 4 turns. Older turns compressed into a running summary via LLM.

---

## 11. Telugu — Scholarship Eligibility

```
$ python -m jantar "నేను SC విద్యార్థిని, ఏ స్కాలర్‌షిప్‌లకు అర్హత ఉంది?"

╭── Answer ──╮
│ SC విద్యార్థులకు అందుబాటులో ఉన్న స్కాలర్‌షిప్‌లు:                 │
│                                                                    │
│ 1. Post-Matric Scholarship (Ministry of Social Justice)            │
│ 2. Pre-Matric Scholarship                                          │
│ 3. National Fellowship (PhD/MPhil)                                 │
│                                                                    │
│ Apply: scholarships.gov.in (NSP Portal)                           │
│                                                                    │
│ [Source: Social Welfare Schemes, Scholarships]                    │
╰────────────╯

Citations: Social Welfare > Scholarships
```

**Classification:** `knowledge_query` | **Domain:** `social_welfare`

---

## 12. Pincode Lookup (Tool: India Post)

```
$ python -m jantar "PIN 110001 mein kaun kaun se post office hain?"

╭── Answer ──╮
│ PIN 110001 (New Delhi) mein post offices:                          │
│                                                                    │
│ 1. Baroda House SO                                                 │
│ 2. Bengali Market SO                                               │
│ 3. Connaught Place SO                                              │
│ 4. Gole Market SO                                                  │
│ 5. Parliament House Annexe SO                                      │
│ ... (21 total post offices)                                        │
│                                                                    │
│ District: Central Delhi | State: Delhi                             │
╰────────────╯

Tools used: india_post_pincode
Pipeline: detect_and_translate → classify → tool_selected → tool_executed → answer_generated
```

**Classification:** `tool_action` | **Domain:** `postal` | **Score:** 0.712

---

## RAG Quality Summary

| # | Language | Query | Type | Reranker Score |
|---|----------|-------|------|----------------|
| 1 | Hindi | Ration card documents | knowledge | 0.998 |
| 2 | English | PM-KISAN eligibility | knowledge | 0.994 |
| 3 | Hinglish | IFSC branch lookup | tool | 0.832 |
| 4 | Bengali | Passport documents | knowledge | 0.971 |
| 5 | Tamil | Ayushman Bharat card | knowledge | 0.991 |
| 6 | English | Weather Mumbai | tool | 0.085 |
| 7 | Hindi | DL documents | knowledge | 0.985 |
| 8 | English | Multi-step (wheat + MSP) | multi_step | — |
| 9 | Marathi | DigiLocker usage | knowledge | 0.996 |
| 10 | Hindi | Follow-up (memory) | knowledge | — |
| 11 | Telugu | SC scholarships | knowledge | 0.87 |
| 12 | Hinglish | Pincode lookup | tool | 0.712 |

**Average knowledge retrieval score: 0.97** (cross-lingual BGE-M3 + reranker)
