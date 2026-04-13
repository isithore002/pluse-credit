# CLAUDE.md — PulseCredit Master Instruction File
# The model MUST read this file before generating ANY code, explanation, or decision.
# When hallucination is suspected, return here and re-anchor to this document.

---

## 1. PROJECT IDENTITY

**Name:** PulseCredit
**Tagline:** Behavioral alternative credit scoring for India's 350M credit-invisible population
**Type:** Full-stack web platform (not a mobile app, not a blockchain project, not a chatbot)
**Target users:** Indian students + gig workers with zero CIBIL score
**Hackathon:** Tech Builders Program 2026 — deadline Apr 17, 2026 @ 2:30 AM IST

---

## 2. THE PROBLEM (anchor stats — never fabricate these)

| Stat | Value | Source |
|------|-------|--------|
| India credit-eligible adults | 1,036 million | TransUnion CIBIL |
| Actively using formal credit | 277 million (27%) | TransUnion CIBIL |
| Actively tracking credit profile | 119 million | TransUnion CIBIL |
| Unbanked adults in India | ~190 million | World Bank |
| Gig workers 2020-21 | 7.7 million | NITI Aayog |
| Gig workers projected 2030 | 23.5 million | NITI Aayog |
| Adults never checked credit score | 45% | ZET Technolabs 2025 |

**Core insight:** People with zero CIBIL score are NOT uncreditworthy — they are *invisible*.
Their UPI transactions reveal behavioral creditworthiness that the formal system ignores entirely.

---

## 3. ARCHITECTURE — NEVER DEVIATE FROM THIS

```
INPUT LAYER
  ├── PDF upload (pdfplumber, multi-bank: HDFC/SBI/ICICI/Kotak)
  ├── CSV upload (PhonePe/GPay export format)
  └── Demo personas (Ravi student / Priya Swiggy / Arjun improving)
        ↓
FEATURE ENGINEERING (24 features → 6 dimensions)
  ├── Dim 1: Payment Rhythm      (CoV, streak, FFT seasonality)
  ├── Dim 2: Merchant Consistency (HHI, retention rate, category entropy)
  ├── Dim 3: Social Trust Graph  (NetworkX: degree centrality, reciprocity)
  ├── Dim 4: Calendar Alignment  (semester detection, stipend fingerprint)
  ├── Dim 5: Velocity Stability  (Z-score, MoM delta, outlier detection)
  └── Dim 6: NLP Intent Score    (spaCy NER + Gemini Flash classification)
        ↓
ML ENSEMBLE (3 models)
  ├── Model A: XGBoost (60% weight) — primary scorer + SHAP
  ├── Model B: PyTorch Autoencoder (25% weight) — anomaly/novelty signal
  │     Architecture: 24→12→6→12→24, Dropout 0.2, Adam, 50 epochs
  └── Heuristic rules (15% weight) — hard guards
        ↓ Weighted blend → Platt scaling → 300–850
LLM LAYER (Gemini Flash 1.5)
  ├── Call 1: Plain-English explanation (score + SHAP top 3 → 2 sentences)
  ├── Call 2: Action roadmap (3 actions with predicted score delta each)
  └── Call 3: Lender credit memo (150-word structured narrative for NBFCs)
        ↓
OUTPUT LAYER (Next.js 14)
  ├── Animated score ring (300–850, Framer Motion)
  ├── 6-axis radar chart (Recharts RadarChart)
  ├── SHAP waterfall chart (Recharts BarChart, sorted by impact)
  ├── What-if simulator (6 sliders → /api/simulate → live score update)
  ├── D3 force-directed social graph (node=contact, edge=transaction freq)
  ├── Score history timeline (Recharts LineChart)
  └── Lender PDF export (ReportLab backend / jsPDF frontend)
```

---

## 4. TECH STACK — EXACT VERSIONS (do not substitute)

### Backend (Python)
```
fastapi==0.111.0
uvicorn[standard]==0.30.0
xgboost==2.0.3
shap==0.45.0
torch==2.3.0
scikit-learn==1.5.0
networkx==3.3
pdfplumber==0.11.0
spacy==3.7.4
google-generativeai==0.7.0
supabase==2.5.0
pandas==2.2.2
numpy==1.26.4
scipy==1.13.0
python-multipart==0.0.9
python-dotenv==1.0.1
reportlab==4.2.0
```

### Frontend (Node)
```
next: 14.2.x
react: 18.3.x
tailwindcss: 3.4.x
recharts: 2.12.x
d3: 7.9.x
react-dropzone: 14.2.x
jspdf: 2.5.x
html2canvas: 1.4.x
framer-motion: 11.2.x
zustand: 4.5.x
@supabase/supabase-js: 2.43.x
axios: 1.7.x
react-hook-form: 7.51.x
```

### Infrastructure
```
Frontend hosting: Vercel (free)
Backend hosting: Render (free tier)
Database: Supabase (PostgreSQL, free tier)
LLM: Gemini Flash 1.5 (free tier - 15 RPM)
CI/CD: GitHub Actions
```

---

## 5. DATABASE SCHEMA (Supabase PostgreSQL)

```sql
-- profiles: one row per scored user
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  archetype TEXT CHECK (archetype IN ('student','gig_worker','salaried','irregular')),
  created_at TIMESTAMPTZ DEFAULT now(),
  is_demo BOOLEAN DEFAULT false
);

-- transactions: raw parsed UPI data
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES profiles(id),
  txn_date DATE NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  direction TEXT CHECK (direction IN ('CR','DR')),
  vpa TEXT,           -- UPI ID of counterparty
  merchant_name TEXT,
  category TEXT,      -- food/transport/rent/education/other
  remarks TEXT,       -- free-text note from statement
  utr TEXT            -- unique transaction reference
);

-- feature_vectors: computed dimensions per profile
CREATE TABLE feature_vectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES profiles(id),
  computed_at TIMESTAMPTZ DEFAULT now(),
  rhythm_score NUMERIC(5,2),
  merchant_score NUMERIC(5,2),
  social_score NUMERIC(5,2),
  calendar_score NUMERIC(5,2),
  velocity_score NUMERIC(5,2),
  nlp_score NUMERIC(5,2),
  raw_features JSONB   -- all 24 raw feature values
);

-- scores: final credit score per profile
CREATE TABLE scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES profiles(id),
  scored_at TIMESTAMPTZ DEFAULT now(),
  pulse_score INTEGER CHECK (pulse_score BETWEEN 300 AND 850),
  confidence_low INTEGER,
  confidence_high INTEGER,
  xgb_score NUMERIC(5,2),
  ae_reconstruction_error NUMERIC(8,4),
  shap_values JSONB,
  explanation TEXT,
  actions JSONB,        -- array of {action, delta, priority}
  lender_memo TEXT
);
```

---

## 6. API CONTRACT (FastAPI — exact endpoint shapes)

### POST /api/parse
```python
# Input: multipart/form-data with file (PDF or CSV) + bank_format
# Output:
{
  "profile_id": "uuid",
  "transaction_count": 87,
  "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
  "transactions": [
    {
      "txn_date": "2024-01-15",
      "amount": 50.00,
      "direction": "DR",
      "vpa": "zomato@upi",
      "merchant_name": "Zomato",
      "category": "food",
      "remarks": "Order #123456"
    }
  ]
}
```

### POST /api/score
```python
# Input: { "profile_id": "uuid" }
# Output:
{
  "pulse_score": 657,
  "confidence_interval": [627, 687],
  "band": "good",          # poor/fair/good/very_good/excellent
  "archetype": "student",
  "dimensions": {
    "rhythm": 72,
    "merchant": 65,
    "social": 55,
    "calendar": 80,
    "velocity": 48,
    "nlp": 60
  },
  "shap_top3": [
    {"feature": "velocity_zscore", "value": -0.34, "impact": -18},
    {"feature": "rhythm_cov", "value": 0.21, "impact": +12},
    {"feature": "social_reciprocity", "value": 0.44, "impact": +9}
  ],
  "explanation": "Your ₹50 daily canteen payments show strong discipline...",
  "actions": [
    {"action": "Make at least one UPI payment every 3 days", "delta": +18, "priority": 1},
    {"action": "Keep monthly spend within 20% of last month", "delta": +14, "priority": 2},
    {"action": "Ask 3 contacts to send you ₹1 each", "delta": +11, "priority": 3}
  ],
  "lender_memo": "Profile Summary: Student archetype..."
}
```

### POST /api/simulate
```python
# Input: { "base_profile_id": "uuid", "overrides": {"rhythm": 85, "velocity": 70} }
# Output: same shape as /api/score but computed in-memory, not saved
# Must respond in < 200ms (use cached feature vector, only re-run ensemble)
```

### GET /api/personas
```python
# Returns array of 3 pre-built demo profiles with full score data
[
  {"id": "ravi-uuid", "name": "Ravi", "archetype": "student", "pulse_score": 612, ...},
  {"id": "priya-uuid", "name": "Priya", "archetype": "gig_worker", "pulse_score": 571, ...},
  {"id": "arjun-uuid", "name": "Arjun", "archetype": "improving", "pulse_score": 701, ...}
]
```

### GET /api/report/{profile_id}
```python
# Returns: PDF binary stream (Content-Type: application/pdf)
# Generated by ReportLab on backend
# Contains: score, radar chart data, actions, lender memo
```

---

## 7. ML MODEL SPECIFICATIONS

### XGBoost parameters
```python
params = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "random_state": 42
}
```

### PyTorch Autoencoder architecture
```python
class CreditAutoencoder(nn.Module):
    # Encoder: 24 → 12 → 6
    # Decoder: 6 → 12 → 24
    # Activation: ReLU (hidden), Sigmoid (output — features are 0-1 normalized)
    # Dropout: 0.2 on all hidden layers
    # Loss: MSELoss (reconstruction)
    # Optimizer: Adam, lr=0.001
    # Epochs: 50
    # Batch size: 32
    # Train on NORMAL profiles only (label != 'defaulted')
    # Reconstruction error threshold for "anomaly": mean + 2*std of training errors
```

### Ensemble weights
```python
ENSEMBLE_WEIGHTS = {
    "xgboost_score": 0.60,
    "ae_novelty_signal": 0.25,   # 1 - normalized_reconstruction_error
    "heuristic_score": 0.15
}
# Final score = weighted_sum → Platt scaling → map to 300-850 range
```

### Synthetic dataset generation
```python
ARCHETYPES = {
    "disciplined_student": {
        "n": 300,
        "rhythm_cov": (0.1, 0.25),       # low CoV = regular
        "monthly_spend": (3000, 8000),
        "merchant_hhi": (0.4, 0.7),       # concentrated = consistent
        "unique_senders": (3, 12),
        "label_range": (650, 820)
    },
    "erratic_gig_worker": {
        "n": 250,
        "rhythm_cov": (0.4, 0.8),
        "monthly_spend": (8000, 25000),
        "merchant_hhi": (0.1, 0.35),
        "unique_senders": (1, 5),
        "label_range": (400, 620)
    },
    "improving": {
        "n": 250,
        "rhythm_cov_trend": "decreasing",  # gets more regular over time
        "label_range": (580, 720)
    },
    "defaulted": {
        "n": 200,
        "rhythm_cov": (0.6, 1.2),
        "label_range": (300, 480)
    }
}
# Total: 1,000 profiles. Split: 70% train / 30% test
```

---

## 8. GEMINI PROMPT TEMPLATES (exact — do not rewrite)

### Prompt 1: Explanation
```
You are a financial advisor explaining a credit score to a first-time borrower in India.

Score: {pulse_score}/850
Top factors (SHAP): {shap_top3_formatted}
User archetype: {archetype}
Weakest dimension: {weakest_dimension} (score: {weakest_score}/100)

Write EXACTLY 2 sentences in simple English (no jargon).
Sentence 1: What is working in their favor with a specific example from their data.
Sentence 2: What is holding them back and why it matters to a lender.

Return JSON: {"explanation": "..."}
```

### Prompt 2: Action roadmap
```
You are a credit coach for a {archetype} in India with PulseCredit score {pulse_score}/850.

Weakest dimensions ranked: {dimensions_sorted_ascending}
Current dimension scores: {dimensions_json}

Generate exactly 3 specific, actionable improvements.
Each must: name the exact behavior, state the timeframe, predict the score increase.
Be hyper-specific — not "pay regularly" but "make at least one UPI payment every 3 days".

Return JSON: {"actions": [{"action": "...", "delta": 18, "priority": 1}, ...]}
```

### Prompt 3: Lender memo
```
You are writing a credit memo for an NBFC loan officer reviewing a first-time borrower.

PulseCredit Score: {pulse_score}/850 ({band})
Confidence interval: {confidence_low}–{confidence_high}
Archetype: {archetype}
Top strengths (SHAP): {top_positive_shap}
Top risks (SHAP): {top_negative_shap}
Dimension breakdown: {dimensions_json}

Write a 150-word structured memo with exactly these sections:
**Profile Summary** | **Positive Signals** | **Risk Indicators** | **Recommendation**

Recommendation must be one of: "Approve up to ₹{amount}" / "Approve with monitoring" / "Decline — reassess in 90 days"

Return JSON: {"lender_memo": "..."}
```

---

## 9. HALLUCINATION GUARD — THINGS TO NEVER DO

❌ Never use Groq API — this project uses Gemini Flash 1.5 only
❌ Never use blockchain, smart contracts, or crypto — this is pure web2
❌ Never use GPT/OpenAI — Gemini only
❌ Never import `tensorflow` — use `torch` (PyTorch)
❌ Never use `Flask` — use `FastAPI`
❌ Never use `MongoDB` — use `Supabase` (PostgreSQL)
❌ Never store raw PDF files in database — store only parsed JSON
❌ Never hardcode API keys — always use `os.getenv()` with `.env`
❌ Never return scores outside 300–850 range
❌ Never generate credit scores without running the ensemble (no shortcuts)
❌ Never skip SHAP computation — it feeds Gemini explanations
❌ Never use `React class components` — hooks only
❌ Never use `pages/` router — use `app/` router (Next.js 14)

---

## 10. FILE STRUCTURE (canonical — match exactly)

```
pulsecredit/
├── backend/
│   ├── main.py                  # FastAPI app, all routers
│   ├── feature_engine.py        # All 24 features, 6 dimensions
│   ├── ensemble.py              # XGBoost + AE + heuristics blend
│   ├── autoencoder.py           # PyTorch model definition + training
│   ├── pdf_parser.py            # pdfplumber, multi-bank support
│   ├── nlp_pipeline.py          # spaCy + Gemini classification
│   ├── social_graph.py          # NetworkX graph builder
│   ├── gemini_client.py         # All 3 Gemini prompts
│   ├── synthetic_data.py        # 1,000 profile generator
│   ├── train.py                 # Model training + evaluation script
│   ├── models/
│   │   ├── model.pkl            # Trained XGBoost
│   │   └── autoencoder.pt       # Trained PyTorch AE
│   ├── data/
│   │   └── synthetic_dataset.csv
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Landing / upload
│   │   ├── dashboard/page.tsx   # Score dashboard
│   │   ├── simulate/page.tsx    # What-if simulator
│   │   ├── graph/page.tsx       # Social graph viz
│   │   └── report/page.tsx      # Lender report
│   ├── components/
│   │   ├── ScoreRing.tsx        # Animated 300-850 ring
│   │   ├── RadarChart.tsx       # 6-axis behavioral radar
│   │   ├── SHAPWaterfall.tsx    # SHAP impact bar chart
│   │   ├── WhatIfSimulator.tsx  # 6 sliders + live score
│   │   ├── SocialGraph.tsx      # D3 force-directed graph
│   │   ├── LenderReport.tsx     # Memo + PDF export
│   │   ├── UploadZone.tsx       # Drag-drop + persona switch
│   │   └── ActionRoadmap.tsx    # 3 ranked improvement cards
│   ├── lib/
│   │   ├── api.ts               # All axios calls to FastAPI
│   │   └── store.ts             # Zustand global state
│   └── package.json
├── db/
│   └── migrations/
│       └── 001_initial_schema.sql
├── notebooks/
│   └── eda_and_training.ipynb
├── .env.example
├── .github/workflows/deploy.yml
├── CLAUDE.md                    # ← THIS FILE
├── INSTRUCTIONS.md              # Feature-level instructions
└── README.md                    # Mermaid diagram + docs
```

---

## 11. SCORE BANDS

| Score | Band | Label | Indicative loan |
|-------|------|-------|-----------------|
| 750–850 | Excellent | `excellent` | Up to ₹1,00,000 |
| 700–749 | Very good | `very_good` | Up to ₹50,000 |
| 650–699 | Good | `good` | Up to ₹25,000 |
| 600–649 | Fair | `fair` | Up to ₹10,000 |
| 300–599 | Poor | `poor` | Decline / ₹5,000 with monitoring |

---

## 12. DEMO PERSONA SPECS

### Ravi (student, score ~612)
- 22 years old, engineering student, Chennai
- Transactions: daily ₹50 canteen, monthly ₹6,000 rent, weekly ₹200-400 Swiggy
- Weak: velocity stability (big spend spike in March for phone), low social senders (only 2 unique)
- Strong: rhythm (pays daily), calendar alignment (semester pattern clear)

### Priya (gig worker, score ~571)
- 28 years old, Swiggy delivery partner, Bengaluru
- Transactions: irregular earnings (₹500-2000 daily), high fuel spend, no fixed rent pattern
- Weak: merchant consistency, calendar alignment, velocity very erratic
- Strong: high transaction volume, some reciprocal transfers with colleagues

### Arjun (improving, score ~701)
- 25 years old, freelancer, Pune — 3 months of visible improvement
- Transactions: rhythm improving month over month, started paying rent on fixed date
- Strong across most dims, improving trajectory visible in history chart
- Purpose: shows the "what-if simulator" working — near excellent band
