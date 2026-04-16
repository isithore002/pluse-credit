"""
main.py - FastAPI app orchestrating the entire PulseCredit pipeline
Endpoints: /api/parse, /api/score, /api/simulate, /api/personas, /api/report
"""

import os
import json
import pickle
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from uuid import UUID
from tempfile import NamedTemporaryFile
import numpy as np
import pandas as pd
import xgboost as xgb
import torch
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from feature_engine import FeatureEngine
from autoencoder import load_model as load_ae_model, get_reconstruction_error
from ensemble import EnsembleScorer, score_profile
from pdf_parser import StatementParser
from gemini_client import GeminiClient

# Initialize FastAPI app
app = FastAPI(
    title="PulseCredit API",
    description="Behavioral credit scoring for India's credit-invisible population",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global models loaded at startup
MODELS_DIR = Path(__file__).parent / "models"
DATA_DIR = Path(__file__).parent / "data"
UPLOAD_TMP_DIR = DATA_DIR / "tmp_uploads"

models_cache = {
    "xgb_model": None,
    "ae_model": None,
    "ae_error_threshold": None,
    "demo_personas": None,
    "feature_scaler": None,
}

supabase_client = None
profile_state_cache: Dict[str, Dict] = {}

FEATURE_ORDER = [
    "rhythm_cov",
    "rhythm_streak",
    "rhythm_recency_ratio",
    "rhythm_weekly_fft",
    "merchant_hhi",
    "merchant_retention",
    "merchant_entropy",
    "merchant_recurring",
    "social_unique_senders",
    "social_sender_ratio",
    "social_reciprocity",
    "social_centrality",
    "calendar_semester_score",
    "calendar_stipend_regularity",
    "calendar_rent_regularity",
    "calendar_festival_adjusted",
    "velocity_zscore",
    "velocity_mom_delta",
    "velocity_outlier_count",
    "velocity_micro_split",
    "nlp_productive_ratio",
    "nlp_org_density",
    "nlp_gemini_intent",
    "nlp_remark_richness",
]

DIMENSION_PREFIXES = ["rhythm", "merchant", "social", "calendar", "velocity", "nlp"]

# Initialize components
feature_engine = FeatureEngine()
parser = StatementParser()
gemini_client = None

device = "cuda" if torch.cuda.is_available() else "cpu"


def is_uuid_like(value: str) -> bool:
    """Return True if value is a valid UUID string."""
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


def is_strict_db_mode() -> bool:
    """Return whether DB connectivity should fail-fast for this runtime."""
    strict_env = os.getenv("STRICT_DB_MODE")
    if strict_env is not None:
        return strict_env.strip().lower() in {"1", "true", "yes", "on"}

    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    return environment in {"production", "staging"}


def _get_supabase_client():
    """Lazy-init Supabase REST config using service role or secret API key credentials."""
    global supabase_client
    if supabase_client is not None:
        return supabase_client

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not service_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept-Profile": "public",
        "Content-Profile": "public",
    }

    base_url = url.rstrip("/")

    try:
        # Probe connectivity and auth at startup; strict DB mode should fail-fast here.
        probe = httpx.get(
            f"{base_url}/rest/v1/profiles",
            params={"select": "id", "limit": 1},
            headers=headers,
            timeout=20,
        )
        if probe.status_code >= 400:
            raise RuntimeError(f"HTTP {probe.status_code}: {probe.text}")

        supabase_client = {
            "base_url": base_url,
            "headers": headers,
        }
    except Exception as e:
        raise RuntimeError(f"Supabase init error: {e}") from e

    return supabase_client


def _supabase_request(
    method: str,
    table: str,
    params: Optional[Dict] = None,
    body: Optional[object] = None,
    prefer: Optional[str] = None,
):
    """Execute a PostgREST request against Supabase."""
    sb = _get_supabase_client()
    headers = dict(sb["headers"])
    if prefer:
        headers["Prefer"] = prefer

    response = httpx.request(
        method,
        f"{sb['base_url']}/rest/v1/{table}",
        params=params,
        json=body,
        headers=headers,
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Supabase {method} {table} failed: HTTP {response.status_code}: {response.text}")

    if response.text:
        try:
            return response.json()
        except ValueError:
            return response.text
    return None


def persist_profile_state(
    profile_id: str,
    archetype: str,
    transactions: List[Dict],
    raw_features: Dict,
    dim_scores: Dict,
    score_payload: Dict,
) -> None:
    """Persist profile scoring artifacts into Supabase tables."""

    score_data = {
        "profile_id": profile_id,
        "pulse_score": int(score_payload["pulse_score"]),
        "confidence_interval": [
            int(score_payload["confidence_interval"][0]),
            int(score_payload["confidence_interval"][1]),
        ],
        "band": get_score_band(int(score_payload["pulse_score"])),
        "dimensions": {k: int(v) for k, v in dim_scores.items()},
        "shap_top3": score_payload.get("shap_top3", []),
        "explanation": score_payload.get("explanation", ""),
        "actions": score_payload.get("actions", []),
        "lender_memo": score_payload.get("lender_memo", ""),
    }
    profile_state_cache[profile_id] = {
        "raw_features": dict(raw_features),
        "dimensions": {k: float(v) for k, v in dim_scores.items()},
        "archetype": archetype,
        "score_data": score_data,
    }

    if not is_uuid_like(profile_id):
        raise ValueError("profile_id must be a valid UUID for DB persistence")

    try:
        _get_supabase_client()
        _supabase_request(
            "POST",
            "profiles",
            body=[
                {
                    "id": profile_id,
                    "archetype": archetype,
                    "is_demo": False,
                }
            ],
            prefer="resolution=merge-duplicates,return=minimal",
        )

        _supabase_request(
            "DELETE",
            "transactions",
            params={"profile_id": f"eq.{profile_id}"},
        )

        txn_rows = []
        for txn in transactions:
            txn_rows.append(
                {
                    "profile_id": profile_id,
                    "txn_date": pd.to_datetime(txn["txn_date"]).strftime("%Y-%m-%d"),
                    "amount": float(txn["amount"]),
                    "direction": txn["direction"],
                    "vpa": txn.get("vpa"),
                    "merchant_name": txn.get("merchant_name"),
                    "category": txn.get("category"),
                    "remarks": txn.get("remarks"),
                    "utr": txn.get("utr"),
                }
            )
        if txn_rows:
            _supabase_request(
                "POST",
                "transactions",
                body=txn_rows,
                prefer="return=minimal",
            )

        _supabase_request(
            "POST",
            "feature_vectors",
            body=[
                {
                    "profile_id": profile_id,
                    "rhythm_score": round(float(dim_scores.get("rhythm", 0)), 2),
                    "merchant_score": round(float(dim_scores.get("merchant", 0)), 2),
                    "social_score": round(float(dim_scores.get("social", 0)), 2),
                    "calendar_score": round(float(dim_scores.get("calendar", 0)), 2),
                    "velocity_score": round(float(dim_scores.get("velocity", 0)), 2),
                    "nlp_score": round(float(dim_scores.get("nlp", 0)), 2),
                    "raw_features": raw_features,
                }
            ],
            prefer="resolution=merge-duplicates,return=minimal",
        )

        _supabase_request(
            "POST",
            "scores",
            body=[
                {
                    "profile_id": profile_id,
                    "pulse_score": int(score_payload["pulse_score"]),
                    "confidence_low": int(score_payload["confidence_interval"][0]),
                    "confidence_high": int(score_payload["confidence_interval"][1]),
                    "shap_values": score_payload.get("shap_top3", []),
                    "explanation": score_payload.get("explanation", ""),
                    "actions": score_payload.get("actions", []),
                    "lender_memo": score_payload.get("lender_memo", ""),
                }
            ],
            prefer="resolution=merge-duplicates,return=minimal",
        )

    except Exception as e:
        if is_strict_db_mode():
            raise RuntimeError(f"Supabase persist error for {profile_id}: {e}") from e
        print(f"[WARN] Supabase persist skipped for {profile_id}: {e}")


def load_profile_state(profile_id: str) -> Dict:
    """Load profile state from Supabase only (strict DB mode)."""
    if profile_id in profile_state_cache:
        return profile_state_cache[profile_id]

    if not is_uuid_like(profile_id):
        return {}

    try:
        _get_supabase_client()
        profile_rows = _supabase_request(
            "GET",
            "profiles",
            params={"select": "archetype", "id": f"eq.{profile_id}", "limit": 1},
        ) or []
        fv_rows = _supabase_request(
            "GET",
            "feature_vectors",
            params={
                "select": "raw_features,rhythm_score,merchant_score,social_score,calendar_score,velocity_score,nlp_score",
                "profile_id": f"eq.{profile_id}",
                "order": "computed_at.desc",
                "limit": 1,
            },
        ) or []
        score_rows = _supabase_request(
            "GET",
            "scores",
            params={
                "select": "pulse_score,confidence_low,confidence_high,shap_values,explanation,actions,lender_memo",
                "profile_id": f"eq.{profile_id}",
                "order": "scored_at.desc",
                "limit": 1,
            },
        ) or []

        if profile_rows and fv_rows and score_rows:
            profile = profile_rows[0]
            fv = fv_rows[0]
            score = score_rows[0]
            pulse_score = int(score.get("pulse_score") or 300)
            loaded = {
                "raw_features": fv.get("raw_features", {}),
                "dimensions": {
                    "rhythm": float(fv.get("rhythm_score") or 0),
                    "merchant": float(fv.get("merchant_score") or 0),
                    "social": float(fv.get("social_score") or 0),
                    "calendar": float(fv.get("calendar_score") or 0),
                    "velocity": float(fv.get("velocity_score") or 0),
                    "nlp": float(fv.get("nlp_score") or 0),
                },
                "archetype": profile.get("archetype", "salaried"),
                "score_data": {
                    "profile_id": profile_id,
                    "pulse_score": pulse_score,
                    "confidence_interval": [
                        int(score.get("confidence_low") or 300),
                        int(score.get("confidence_high") or 330),
                    ],
                    "band": get_score_band(pulse_score),
                    "ai_insights_mode": "fallback",
                    "dimensions": {
                        "rhythm": int(float(fv.get("rhythm_score") or 0)),
                        "merchant": int(float(fv.get("merchant_score") or 0)),
                        "social": int(float(fv.get("social_score") or 0)),
                        "calendar": int(float(fv.get("calendar_score") or 0)),
                        "velocity": int(float(fv.get("velocity_score") or 0)),
                        "nlp": int(float(fv.get("nlp_score") or 0)),
                    },
                    "shap_top3": score.get("shap_values") or [],
                    "explanation": score.get("explanation") or "",
                    "actions": score.get("actions") or [],
                    "lender_memo": score.get("lender_memo") or "",
                },
            }
            profile_state_cache[profile_id] = loaded
            return loaded
    except Exception as e:
        if is_strict_db_mode():
            raise RuntimeError(f"Supabase read error for {profile_id}: {e}") from e
        print(f"[WARN] Supabase read skipped for {profile_id}: {e}")
        return profile_state_cache.get(profile_id, {})

    return {}


def get_score_band(score: int) -> str:
    """Map pulse score to canonical band labels."""
    if score >= 750:
        return "excellent"
    if score >= 700:
        return "very_good"
    if score >= 650:
        return "good"
    if score >= 600:
        return "fair"
    return "poor"


def _fallback_explanation(
    pulse_score: int,
    archetype: str,
    weakest_dimension: str,
    weakest_score: float,
    transaction_count: int,
) -> str:
    """Generate a specific, non-generic explanation when live AI is unavailable."""
    strengths = {
        "student": "routine low-ticket UPI activity that builds repayment visibility",
        "gig_worker": "high transaction activity showing active income movement",
        "salaried": "stable month-on-month spending and predictable payment rhythm",
    }
    weakness_hint = {
        "rhythm": "irregular payment cadence",
        "merchant": "scattered merchant behavior",
        "social": "limited reciprocal transfers",
        "calendar": "weak fixed-date pattern",
        "velocity": "volatile spend spikes",
        "nlp": "unclear transaction intent labels",
    }

    strength_line = strengths.get(archetype, "consistent UPI behavior")
    weak_line = weakness_hint.get(weakest_dimension, weakest_dimension)

    return (
        f"PulseCredit used {transaction_count} UPI transactions to score you at {pulse_score}/850, and your profile shows {strength_line}. "
        f"Your weakest area is {weakest_dimension} ({weakest_score:.0f}/100) due to {weak_line}, which matters because lenders look for predictable cash-flow behavior before approving first-time borrowers."
    )


def _fallback_actions(dimensions: Dict[str, float], archetype: str) -> List[Dict]:
    """Generate 3 practical, benefit-led actions when live AI is unavailable."""
    weakest = min(dimensions.items(), key=lambda x: x[1])[0] if dimensions else "rhythm"

    action_map = {
        "rhythm": [
            {
                "action": "For the next 30 days, make at least one UPI transaction every 3 days so your repayment rhythm appears reliable to lenders.",
                "delta": 18,
                "priority": 1,
            },
            {
                "action": "For the next 2 billing cycles, keep monthly debit spend within +/-20% of last month to show stable budgeting behavior.",
                "delta": 14,
                "priority": 2,
            },
            {
                "action": "Within 21 days, add 3 recurring utility or education payments via UPI to strengthen transaction consistency signals.",
                "delta": 11,
                "priority": 3,
            },
        ],
        "velocity": [
            {
                "action": "For the next 45 days, avoid single debit spikes above your weekly average by splitting large payments across planned dates.",
                "delta": 19,
                "priority": 1,
            },
            {
                "action": "Set a fixed weekly UPI budget and stay within it for 6 weeks to reduce volatility in cash-flow signals.",
                "delta": 13,
                "priority": 2,
            },
            {
                "action": "Move discretionary purchases to a single day each week for 1 month to create a cleaner spend pattern for underwriting models.",
                "delta": 10,
                "priority": 3,
            },
        ],
        "social": [
            {
                "action": "In the next 30 days, maintain at least 3 reciprocal UPI exchanges with trusted contacts to improve social trust signals.",
                "delta": 16,
                "priority": 1,
            },
            {
                "action": "Ask regular payers to keep transfer timings consistent over 6 weeks so inflow reliability becomes visible.",
                "delta": 12,
                "priority": 2,
            },
            {
                "action": "Tag peer transfers clearly (rent split, food, travel) for 1 month to improve intent and relationship quality in your graph.",
                "delta": 9,
                "priority": 3,
            },
        ],
    }

    generic = [
        {
            "action": "For 30 days, maintain regular UPI activity every week to build an auditable credit behavior trail.",
            "delta": 15,
            "priority": 1,
        },
        {
            "action": "For 2 months, keep spend variability low and avoid sudden outlier transactions to improve score stability.",
            "delta": 12,
            "priority": 2,
        },
        {
            "action": "Improve transaction remarks and category consistency over 4 weeks so lenders can interpret your cash-flow intent faster.",
            "delta": 9,
            "priority": 3,
        },
    ]

    # Personalize one action by archetype context.
    selected = action_map.get(weakest, generic)
    if archetype == "student":
        selected[2]["action"] = "For the next semester month, pay canteen/rent/fees on predictable dates so lenders can see disciplined student cash-flow patterns."
    elif archetype == "gig_worker":
        selected[1]["action"] = "For the next 6 weeks, route fuel and work-expense payments through consistent intervals to reduce gig-income volatility risk."

    return selected


def _fallback_lender_memo(
    pulse_score: int,
    band: str,
    confidence_low: int,
    confidence_high: int,
    archetype: str,
    dimensions: Dict[str, float],
) -> str:
    """Generate a structured lender memo with clear real-world context."""
    weakest_dim = min(dimensions.items(), key=lambda x: x[1])[0] if dimensions else "velocity"
    recommendation = "Approve with monitoring"
    if pulse_score >= 750:
        recommendation = "Approve up to ₹100000"
    elif pulse_score >= 700:
        recommendation = "Approve up to ₹50000"
    elif pulse_score < 600:
        recommendation = "Decline — reassess in 90 days"

    return (
        f"Profile Summary: {archetype} borrower scored {pulse_score}/850 ({band}) with confidence range {confidence_low}-{confidence_high}. "
        f"PulseCredit is designed for credit-invisible users and evaluates UPI behavior where bureau history is missing. "
        "Positive Signals: The profile shows repeat digital payment behavior and usable transaction intent patterns, supporting early-stage credit visibility. "
        f"Risk Indicators: The weakest dimension is {weakest_dim}, indicating limited consistency in one key behavioral axis and moderate repayment uncertainty. "
        f"Recommendation: {recommendation}."
    )


def _sanitize_actions(actions: List[Dict], dimensions: Dict[str, float], archetype: str) -> List[Dict]:
    """Guarantee 3 clean roadmap actions with deltas and priorities."""
    cleaned = []
    for idx, item in enumerate(actions or []):
        if not isinstance(item, dict):
            continue
        action_text = str(item.get("action", "")).strip()
        if not action_text:
            continue
        delta = int(item.get("delta", 0) or 0)
        priority = int(item.get("priority", idx + 1) or (idx + 1))
        cleaned.append({
            "action": action_text,
            "delta": max(1, min(30, delta if delta else 10)),
            "priority": max(1, min(3, priority)),
        })

    cleaned = sorted(cleaned, key=lambda x: x["priority"])[:3]
    if len(cleaned) < 3:
        return _fallback_actions(dimensions, archetype)
    return cleaned


@app.on_event("startup")
def load_models():
    """Load trained models on startup"""
    global gemini_client

    try:
        # Load XGBoost
        xgb_path = MODELS_DIR / "model.pkl"
        if xgb_path.exists():
            models_cache["xgb_model"] = xgb.Booster(model_file=str(xgb_path))
            print("[OK] XGBoost model loaded")
        else:
            print("[WARN] XGBoost model not found - run: python backend/train.py")

        # Load Autoencoder
        ae_path = MODELS_DIR / "autoencoder.pt"
        if ae_path.exists():
            models_cache["ae_model"] = load_ae_model(str(ae_path), device=device)
            print("[OK] Autoencoder model loaded")

        # Load AE error threshold
        ae_threshold_path = MODELS_DIR / "ae_error_threshold.pkl"
        if ae_threshold_path.exists():
            with open(ae_threshold_path, "rb") as f:
                threshold_data = pickle.load(f)
                models_cache["ae_error_threshold"] = threshold_data["threshold"]
            print("[OK] AE error threshold loaded")

        # Load demo personas
        personas_path = MODELS_DIR / "demo_personas.pkl"
        if personas_path.exists():
            with open(personas_path, "rb") as f:
                models_cache["demo_personas"] = pickle.load(f)
            print("[OK] Demo personas loaded")

        # Load feature scaler
        scaler_path = MODELS_DIR / "feature_scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                models_cache["feature_scaler"] = pickle.load(f)
            print("[OK] Feature scaler loaded")

        # Initialize Gemini client
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            gemini_client = GeminiClient(api_key=api_key)
            print("[OK] Gemini client initialized (lazy availability check)")
        else:
            print("[WARN] GEMINI_API_KEY not set - Gemini explanations will use defaults")

        try:
            _get_supabase_client()
            print("[OK] Supabase client initialized")
        except Exception as supabase_error:
            if is_strict_db_mode():
                raise
            print(f"[WARN] Supabase unavailable in local mode: {supabase_error}")

    except Exception as e:
        print(f"Model loading error: {e}")
        raise


# Pydantic models for request/response
class ParseRequest(BaseModel):
    bank_format: str = "GENERIC"


class ScoreRequest(BaseModel):
    profile_id: str
    transactions: Optional[List[Dict]] = None


class SimulateRequest(BaseModel):
    profile_id: Optional[str] = None
    base_profile_id: Optional[str] = None
    overrides: Dict[str, float]


class TransactionSchema(BaseModel):
    txn_date: str
    amount: float
    direction: str
    vpa: str
    merchant_name: str
    category: str
    remarks: str


class ParseResponse(BaseModel):
    profile_id: str
    transaction_count: int
    date_range: Dict
    transactions: List[TransactionSchema]


class DimensionScores(BaseModel):
    rhythm: int
    merchant: int
    social: int
    calendar: int
    velocity: int
    nlp: int


class ShapValue(BaseModel):
    feature: str
    value: float
    impact: float


class ScoreResponse(BaseModel):
    profile_id: str
    pulse_score: int
    confidence_interval: List[int]
    band: str
    archetype: str
    ai_insights_mode: str
    dimensions: DimensionScores
    shap_top3: List[Dict]
    explanation: str
    actions: List[Dict]
    lender_memo: str


# ============ ENDPOINTS ============


@app.get("/health")
@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/parse", response_model=ParseResponse)
@app.post("/api/p", response_model=ParseResponse)
async def parse_statement(
    file: UploadFile = File(...),
    bank_format: str = "GENERIC",
    pdf_password: str = "",
):
    """
    Parse UPI statement (PDF or CSV)
    Returns parsed transactions
    """
    try:
        suffix = Path(file.filename).suffix if file.filename else ""
        UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(UPLOAD_TMP_DIR)) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        try:
            # Parse based on file type
            if (file.filename or "").lower().endswith(".pdf"):
                profile_id, transactions = parser.parse_pdf(temp_path, bank_format, pdf_password)
            else:
                profile_id, transactions = parser.parse_csv(temp_path, bank_format)

            # Extract date range
            dates = [pd.to_datetime(t["txn_date"]) for t in transactions]
            date_range = {
                "start": min(dates).strftime("%Y-%m-%d"),
                "end": max(dates).strftime("%Y-%m-%d"),
            }

            normalized_transactions = []
            for txn in transactions:
                normalized_txn = dict(txn)
                normalized_txn["txn_date"] = pd.to_datetime(txn["txn_date"]).strftime("%Y-%m-%d")
                normalized_transactions.append(normalized_txn)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return ParseResponse(
            profile_id=profile_id,
            transaction_count=len(transactions),
            date_range=date_range,
            transactions=normalized_transactions,
        )

    except OSError as e:
        if getattr(e, "errno", None) == 28:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient disk space while processing upload. "
                    f"Clear space on drive containing {UPLOAD_TMP_DIR} and retry."
                ),
            )
        detail = str(e) or repr(e)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        detail = str(e) or repr(e)
        raise HTTPException(status_code=400, detail=detail)


@app.post("/api/score", response_model=ScoreResponse)
async def compute_score(request: ScoreRequest):
    """
    Compute full credit score with explanations
    """
    try:
        if not request.transactions:
            raise ValueError("transactions required")

        # Convert to DataFrame
        txns_list = []
        for txn in request.transactions:
            txns_list.append({
                "profile_id": request.profile_id,
                "txn_date": pd.to_datetime(txn["txn_date"]),
                "amount": float(txn["amount"]),
                "direction": txn["direction"],
                "vpa": txn["vpa"],
                "merchant_name": txn["merchant_name"],
                "category": txn["category"],
                "remarks": txn["remarks"],
            })

        df = pd.DataFrame(txns_list)

        # Compute features
        raw_features_dict, dim_scores = feature_engine.compute_all_features(df, request.profile_id)

        # Extract feature vector
        feature_vector = [raw_features_dict.get(name, 0.5) for name in FEATURE_ORDER]

        # Normalize features
        if models_cache["feature_scaler"]:
            scaler = models_cache["feature_scaler"]
            features_scaled = scaler.transform(np.array(feature_vector).reshape(1, -1))[0]
        else:
            features_scaled = np.clip(np.array(feature_vector), 0, 1)

        # Score
        if not models_cache["xgb_model"]:
            raise ValueError("XGBoost model not loaded - run: python backend/train.py")

        result = score_profile(
            features_scaled,
            models_cache["xgb_model"],
            models_cache["ae_model"],
            models_cache.get("ae_error_threshold", 0.05),
        )

        pulse_score = result["pulse_score"]
        conf_low, conf_high = result["confidence_interval"]

        # Detect archetype
        total_spend = df[df["direction"] == "DR"]["amount"].sum()
        regularity = dim_scores.get("rhythm", 50)
        if regularity > 70:
            archetype = "student"
        elif total_spend > 15000:
            archetype = "gig_worker"
        else:
            archetype = "salaried"

        # Get weakest dimension
        weakest_dim_name = min(dim_scores.items(), key=lambda x: x[1])

        # Generate Gemini explanations (if available)
        explanation = _fallback_explanation(
            pulse_score=pulse_score,
            archetype=archetype,
            weakest_dimension=weakest_dim_name[0],
            weakest_score=weakest_dim_name[1],
            transaction_count=len(request.transactions),
        )
        actions = _fallback_actions(dim_scores, archetype)
        lender_memo = _fallback_lender_memo(
            pulse_score=pulse_score,
            band=result["band"],
            confidence_low=conf_low,
            confidence_high=conf_high,
            archetype=archetype,
            dimensions=dim_scores,
        )
        ai_insights_mode = "fallback"

        shap_values = result.get("shap_top3", [])

        if gemini_client and gemini_client.is_available:
            try:
                explanation = gemini_client.generate_explanation(
                    pulse_score=pulse_score,
                    shap_values=shap_values,
                    archetype=archetype,
                    weakest_dimension=weakest_dim_name[0],
                    weakest_score=weakest_dim_name[1],
                )

                actions = gemini_client.generate_actions(
                    pulse_score=pulse_score,
                    archetype=archetype,
                    dimensions_sorted=dim_scores,
                )
                actions = _sanitize_actions(actions, dim_scores, archetype)

                lender_memo = gemini_client.generate_lender_memo(
                    pulse_score=pulse_score,
                    band=result["band"],
                    confidence_low=conf_low,
                    confidence_high=conf_high,
                    archetype=archetype,
                    shap_values=shap_values,
                    dimensions=dim_scores,
                )
                if not isinstance(lender_memo, str) or len(lender_memo.strip()) < 50:
                    lender_memo = _fallback_lender_memo(
                        pulse_score=pulse_score,
                        band=result["band"],
                        confidence_low=conf_low,
                        confidence_high=conf_high,
                        archetype=archetype,
                        dimensions=dim_scores,
                    )
                ai_insights_mode = "live"
            except Exception as gemini_error:
                print(f"Gemini error: {gemini_error}")

        response_payload = {
            "profile_id": request.profile_id,
            "pulse_score": pulse_score,
            "confidence_interval": [conf_low, conf_high],
            "band": result["band"],
            "archetype": archetype,
            "ai_insights_mode": ai_insights_mode,
            "dimensions": {k: int(v) for k, v in dim_scores.items()},
            "shap_top3": shap_values,
            "explanation": explanation,
            "actions": actions,
            "lender_memo": lender_memo,
        }

        persist_profile_state(
            profile_id=request.profile_id,
            archetype=archetype,
            transactions=request.transactions,
            raw_features=raw_features_dict,
            dim_scores=dim_scores,
            score_payload=response_payload,
        )

        return ScoreResponse(
            profile_id=request.profile_id,
            pulse_score=pulse_score,
            confidence_interval=[conf_low, conf_high],
            band=result["band"],
            archetype=archetype,
            ai_insights_mode=ai_insights_mode,
            dimensions=DimensionScores(**{k: int(v) for k, v in dim_scores.items()}),
            shap_top3=shap_values,
            explanation=explanation,
            actions=actions,
            lender_memo=lender_memo,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/simulate")
async def simulate_score(request: SimulateRequest):
    """
    What-if simulation - compute score with overridden dimensions
    Must respond < 200ms
    """
    try:
        profile_id = request.profile_id or request.base_profile_id
        if not profile_id:
            raise ValueError("profile_id or base_profile_id is required")

        loaded_state = load_profile_state(profile_id)
        if not loaded_state:
            raise ValueError("Profile not found. Run /api/score first.")
        if not models_cache["xgb_model"]:
            raise ValueError("XGBoost model not loaded - run: python backend/train.py")

        raw_features = dict(loaded_state["raw_features"])
        sim_dimensions = dict(loaded_state["dimensions"])
        archetype = loaded_state["archetype"]
        base_score_data = loaded_state["score_data"]

        for dim_name, target in request.overrides.items():
            if dim_name not in DIMENSION_PREFIXES:
                continue
            target_value = float(np.clip(target, 0, 100))
            current_value = max(float(sim_dimensions.get(dim_name, 50.0)), 1.0)
            ratio = target_value / current_value
            sim_dimensions[dim_name] = target_value

            for feature_name in FEATURE_ORDER:
                if feature_name.startswith(f"{dim_name}_"):
                    raw_val = float(raw_features.get(feature_name, 0.5))
                    raw_features[feature_name] = float(np.clip(raw_val * ratio, 0, 1))

        feature_vector = np.array([raw_features.get(name, 0.5) for name in FEATURE_ORDER], dtype=np.float32)

        if models_cache["feature_scaler"]:
            feature_vector = models_cache["feature_scaler"].transform(feature_vector.reshape(1, -1))[0]

        result = score_profile(
            feature_vector,
            models_cache["xgb_model"],
            models_cache["ae_model"],
            models_cache.get("ae_error_threshold", 0.05),
        )

        simulated = {
            "profile_id": profile_id,
            "pulse_score": result["pulse_score"],
            "confidence_interval": result["confidence_interval"],
            "band": result["band"],
            "archetype": archetype,
            "ai_insights_mode": base_score_data.get("ai_insights_mode", "fallback"),
            "dimensions": {k: int(v) for k, v in sim_dimensions.items()},
            "shap_top3": result.get("shap_top3", []),
            "explanation": "This score reflects your overridden behavioral dimensions.",
            "actions": base_score_data.get("actions", []),
            "lender_memo": "Simulated profile for planning only.",
            "base_pulse_score": base_score_data.get("pulse_score"),
            "delta": result["pulse_score"] - int(base_score_data.get("pulse_score", 0)),
        }

        return simulated

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/personas")
def get_demo_personas():
    """
    Get 3 demo personas with full score data
    """
    if not models_cache["demo_personas"]:
        raise HTTPException(status_code=404, detail="Demo personas not available")

    personas_list = []
    for key, persona in models_cache["demo_personas"].items():
        shap_raw = persona.get("shap_top3", [])
        if isinstance(shap_raw, dict):
            shap_raw = [
                {
                    "feature": item.get("feature") or item.get("name", "unknown_feature"),
                    "value": item.get("value", 0.0),
                    "impact": item.get("impact", 0.0),
                }
                for item in shap_raw.values()
            ]
        persona["shap_top3"] = shap_raw
        personas_list.append(persona)

    return personas_list


@app.get("/api/report/{profile_id}")
def get_lender_report(profile_id: str, background_tasks: BackgroundTasks):
    """
    Generate PDF lender report
    Returns binary PDF stream
    """
    try:
        loaded_state = load_profile_state(profile_id)
        score_data = loaded_state.get("score_data") if loaded_state else None
        if not score_data:
            raise HTTPException(status_code=404, detail="Profile score not found. Run /api/score first.")

        with NamedTemporaryFile(delete=False, suffix=f"_{profile_id}.pdf") as tmp_file:
            pdf_path = tmp_file.name

        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        y = height - 50

        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, "PulseCredit Lender Report")
        y -= 30

        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Profile ID: {profile_id}")
        y -= 18
        c.drawString(40, y, f"Score: {score_data['pulse_score']} ({score_data['band']})")
        y -= 18
        c.drawString(40, y, f"Confidence: {score_data['confidence_interval'][0]} - {score_data['confidence_interval'][1]}")
        y -= 24

        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Dimensions")
        y -= 18
        c.setFont("Helvetica", 11)
        for dim, val in score_data.get("dimensions", {}).items():
            c.drawString(50, y, f"- {dim}: {val}")
            y -= 16

        y -= 8
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Action Roadmap")
        y -= 18
        c.setFont("Helvetica", 11)
        for action in score_data.get("actions", [])[:3]:
            c.drawString(50, y, f"- {action.get('action', '')} (+{action.get('delta', 0)})")
            y -= 16

        y -= 8
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Lender Memo")
        y -= 18
        c.setFont("Helvetica", 10)
        for line in str(score_data.get("lender_memo", "")).split("\n"):
            if y < 40:
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", 10)
            c.drawString(50, y, line[:110])
            y -= 14

        c.save()
        background_tasks.add_task(os.remove, pdf_path)

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"pulsecredit-report-{profile_id}.pdf",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ MAIN ============


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
