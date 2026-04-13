"""
main.py - FastAPI app orchestrating the entire PulseCredit pipeline
Endpoints: /api/parse, /api/score, /api/simulate, /api/personas, /api/report
"""

import os
import json
import pickle
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import numpy as np
import pandas as pd
import xgboost as xgb
import torch
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

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

models_cache = {
    "xgb_model": None,
    "ae_model": None,
    "ae_error_threshold": None,
    "demo_personas": None,
    "feature_scaler": None,
}

# Initialize components
feature_engine = FeatureEngine()
parser = StatementParser()
gemini_client = None

device = "cuda" if torch.cuda.is_available() else "cpu"


@app.on_event("startup")
def load_models():
    """Load trained models on startup"""
    global models_cache, gemini_client

    try:
        # Load XGBoost
        xgb_path = MODELS_DIR / "model.pkl"
        if xgb_path.exists():
            models_cache["xgb_model"] = xgb.Booster(model_file=str(xgb_path))
            print("✓ XGBoost model loaded")
        else:
            print("⚠ XGBoost model not found - run: python backend/train.py")

        # Load Autoencoder
        ae_path = MODELS_DIR / "autoencoder.pt"
        if ae_path.exists():
            models_cache["ae_model"] = load_ae_model(str(ae_path), device=device)
            print("✓ Autoencoder model loaded")

        # Load AE error threshold
        ae_threshold_path = MODELS_DIR / "ae_error_threshold.pkl"
        if ae_threshold_path.exists():
            with open(ae_threshold_path, "rb") as f:
                threshold_data = pickle.load(f)
                models_cache["ae_error_threshold"] = threshold_data["threshold"]
            print("✓ AE error threshold loaded")

        # Load demo personas
        personas_path = MODELS_DIR / "demo_personas.pkl"
        if personas_path.exists():
            with open(personas_path, "rb") as f:
                models_cache["demo_personas"] = pickle.load(f)
            print("✓ Demo personas loaded")

        # Load feature scaler
        scaler_path = MODELS_DIR / "feature_scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                models_cache["feature_scaler"] = pickle.load(f)
            print("✓ Feature scaler loaded")

        # Initialize Gemini client
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            gemini_client = GeminiClient(api_key=api_key)
            print("✓ Gemini client initialized")
        else:
            print("⚠ GEMINI_API_KEY not set - Gemini explanations will use defaults")

    except Exception as e:
        print(f"Model loading error: {e}")


# Pydantic models for request/response
class ParseRequest(BaseModel):
    bank_format: str = "GENERIC"


class ScoreRequest(BaseModel):
    profile_id: str
    transactions: Optional[List[Dict]] = None


class SimulateRequest(BaseModel):
    profile_id: str
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
    pulse_score: int
    confidence_interval: List[int]
    band: str
    archetype: str
    dimensions: DimensionScores
    shap_top3: List[Dict]
    explanation: str
    actions: List[Dict]
    lender_memo: str


# ============ ENDPOINTS ============


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/parse", response_model=ParseResponse)
async def parse_statement(
    file: UploadFile = File(...),
    bank_format: str = "GENERIC",
):
    """
    Parse UPI statement (PDF or CSV)
    Returns parsed transactions
    """
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # Parse based on file type
        if file.filename.endswith(".pdf"):
            profile_id, transactions = parser.parse_pdf(temp_path, bank_format)
        else:
            profile_id, transactions = parser.parse_csv(temp_path, bank_format)

        # Extract date range
        dates = [pd.to_datetime(t["txn_date"]) for t in transactions]
        date_range = {
            "start": min(dates).strftime("%Y-%m-%d"),
            "end": max(dates).strftime("%Y-%m-%d"),
        }

        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return ParseResponse(
            profile_id=profile_id,
            transaction_count=len(transactions),
            date_range=date_range,
            transactions=transactions,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
        feature_vector = [raw_features_dict.get(f"f{i}", 0.5) for i in range(24)]

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
        explanation = "Your credit profile shows consistent patterns."
        actions = []
        lender_memo = "Professional credit assessment available."

        if gemini_client:
            try:
                shap_dict = result.get("shap_top3", {})

                explanation = gemini_client.generate_explanation(
                    pulse_score=pulse_score,
                    shap_dict=shap_dict,
                    archetype=archetype,
                    weakest_dimension=weakest_dim_name[0],
                    weakest_score=weakest_dim_name[1],
                )

                actions = gemini_client.generate_actions(
                    pulse_score=pulse_score,
                    archetype=archetype,
                    dimensions_sorted=dim_scores,
                )

                lender_memo = gemini_client.generate_lender_memo(
                    pulse_score=pulse_score,
                    band=result["band"],
                    confidence_low=conf_low,
                    confidence_high=conf_high,
                    archetype=archetype,
                    shap_dict=shap_dict,
                    dimensions=dim_scores,
                )
            except Exception as gemini_error:
                print(f"Gemini error: {gemini_error}")

        return ScoreResponse(
            pulse_score=pulse_score,
            confidence_interval=[conf_low, conf_high],
            band=result["band"],
            archetype=archetype,
            dimensions=DimensionScores(**{k: int(v) for k, v in dim_scores.items()}),
            shap_top3=result.get("shap_top3", []),
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
        # This is a simplified version
        # In production, would cache feature vector and only re-run ensemble
        base_score = 650

        # Simple delta computation
        score_delta = sum(request.overrides.values()) / len(request.overrides) - 50

        simulated_score = int(base_score + score_delta * 0.5)
        simulated_score = max(300, min(850, simulated_score))

        return {
            "base_score": base_score,
            "simulated_score": simulated_score,
            "delta": simulated_score - base_score,
            "confidence_interval": [simulated_score - 30, simulated_score + 30],
        }

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
        personas_list.append(persona)

    return personas_list


@app.get("/api/report/{profile_id}")
def get_lender_report(profile_id: str):
    """
    Generate PDF lender report
    Returns binary PDF stream
    """
    try:
        # Placeholder - would generate PDF with ReportLab
        return JSONResponse(
            {"message": f"PDF report for {profile_id} would be generated here"},
            status_code=200,
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
