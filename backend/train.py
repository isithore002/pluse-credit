"""
train.py - Train XGBoost + Autoencoder models and generate demo personas
Run: python backend/train.py
"""

import os
import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
import torch
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from pathlib import Path

from synthetic_data import generate_synthetic_dataset
from feature_engine import FeatureEngine
from autoencoder import train_autoencoder, save_model as save_ae_model
from ensemble import EnsembleScorer, score_profile


def prepare_feature_matrix(
    transactions_df: pd.DataFrame, profiles_df: pd.DataFrame
) -> tuple:
    """
    Compute features for all profiles and create training matrices
    Returns: (X, y, profiles_with_features)
    """
    print("Computing features for all profiles...")

    engine = FeatureEngine()
    all_raw_features = []
    all_labels = []
    profile_data = []

    for profile_id in profiles_df["profile_id"].unique():
        # Get transactions for this profile
        profile_txns = transactions_df[transactions_df["profile_id"] == profile_id].copy()
        profile_txns["txn_date"] = pd.to_datetime(profile_txns["txn_date"])

        if len(profile_txns) < 5:  # Skip profiles with too few transactions
            continue

        # Compute features
        raw_features_dict, dim_scores = engine.compute_all_features(profile_txns, profile_id)

        # Extract feature vector in order
        feature_names = engine._get_feature_names() if hasattr(engine, "_get_feature_names") else [
            f"f{i}" for i in range(24)
        ]

        # Better: extract values in consistent order
        feature_vector = []
        for key in sorted(raw_features_dict.keys()):
            feature_vector.append(raw_features_dict[key])

        if len(feature_vector) != 24:
            # Pad or trim to 24 features
            feature_vector = feature_vector[:24] + [0.5] * (24 - len(feature_vector))

        all_raw_features.append(feature_vector)

        # Get label (ground truth score)
        profile_label = profiles_df[profiles_df["profile_id"] == profile_id]["pulse_score"].values[0]
        all_labels.append(profile_label)

        profile_data.append({
            "profile_id": profile_id,
            "features": feature_vector,
            "dim_scores": dim_scores,
            "label": profile_label,
        })

    # Convert to numpy arrays
    X = np.array(all_raw_features, dtype=np.float32)
    y = np.array(all_labels, dtype=np.float32)

    # Normalize to 0-1
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # Normalize labels to 0-1 (300-850 range)
    y_normalized = (y - 300) / 550

    print(f"✓ Features computed for {len(X)} profiles")
    print(f"  Feature shape: {X_scaled.shape}")
    print(f"  Label range: {y.min():.0f} - {y.max():.0f}")

    return X_scaled, y_normalized, y, profile_data, scaler


def train_xgboost(X_train: np.ndarray, y_train: np.ndarray) -> xgb.Booster:
    """Train XGBoost model"""
    print("\nTraining XGBoost model...")

    dtrain = xgb.DMatrix(X_train, label=y_train)

    params = {
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": 42,
    }

    model = xgb.train(
        params,
        dtrain,
        num_boost_round=300,
        verbose_eval=50,
    )

    print("✓ XGBoost model trained")
    return model


def train_pytorch_ae(
    X_train: np.ndarray, X_val: np.ndarray, device: str = "cpu"
) -> tuple:
    """Train PyTorch autoencoder"""
    print("\nTraining PyTorch Autoencoder...")

    # Train only on "normal" profiles (exclude outliers)
    ae_model, ae_error_mean, ae_error_std = train_autoencoder(
        X_train, X_val, epochs=50, batch_size=32, learning_rate=0.001, device=device
    )

    return ae_model, ae_error_mean, ae_error_std


def generate_demo_personas(
    profiles_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    xgb_model: xgb.Booster,
    ae_model,
    ae_error_threshold: float,
    scaler,
    all_features: list,
    all_labels: np.ndarray,
) -> Dict:
    """
    Generate or select demo personas: Ravi (student), Priya (gig), Arjun (improving)
    """
    print("\nGenerating demo personas...")

    demo_personas = {}

    # RAVI: disciplined student (target: ~612)
    student_profiles = profiles_df[profiles_df["archetype"] == "disciplined_student"]
    if len(student_profiles) > 0:
        ravi_idx = student_profiles.index[0]
        ravi_profile_id = student_profiles.iloc[0]["profile_id"]

        # Find feature vector for Ravi
        for pdata in all_features:
            if pdata["profile_id"] == ravi_profile_id:
                features = np.array(pdata["features"], dtype=np.float32)
                features_scaled = scaler.transform(features.reshape(1, -1))[0]

                # Score
                result = score_profile(features_scaled, xgb_model, ae_model, ae_error_threshold)
                pdata["pulse_score"] = result["pulse_score"]
                pdata["band"] = result["band"]
                pdata["shap"] = result["shap_top3"]

                demo_personas["ravi"] = {
                    "id": ravi_profile_id,
                    "name": "Ravi",
                    "archetype": "student",
                    "age": 22,
                    "occupation": "Engineering Student",
                    "city": "Chennai",
                    "pulse_score": result["pulse_score"],
                    "band": result["band"],
                    "confidence": [result["confidence_interval"][0], result["confidence_interval"][1]],
                    "dimensions": pdata["dim_scores"],
                    "shap_top3": result["shap_top3"],
                }
                break

    # PRIYA: erratic gig worker (target: ~571)
    gig_profiles = profiles_df[profiles_df["archetype"] == "erratic_gig_worker"]
    if len(gig_profiles) > 0:
        priya_profile_id = gig_profiles.iloc[0]["profile_id"]

        for pdata in all_features:
            if pdata["profile_id"] == priya_profile_id:
                features = np.array(pdata["features"], dtype=np.float32)
                features_scaled = scaler.transform(features.reshape(1, -1))[0]

                result = score_profile(features_scaled, xgb_model, ae_model, ae_error_threshold)
                pdata["pulse_score"] = result["pulse_score"]
                pdata["band"] = result["band"]
                pdata["shap"] = result["shap_top3"]

                demo_personas["priya"] = {
                    "id": priya_profile_id,
                    "name": "Priya",
                    "archetype": "gig_worker",
                    "age": 28,
                    "occupation": "Swiggy Delivery Partner",
                    "city": "Bengaluru",
                    "pulse_score": result["pulse_score"],
                    "band": result["band"],
                    "confidence": [result["confidence_interval"][0], result["confidence_interval"][1]],
                    "dimensions": pdata["dim_scores"],
                    "shap_top3": result["shap_top3"],
                }
                break

    # ARJUN: improving trajectory (target: ~701)
    improving_profiles = profiles_df[profiles_df["archetype"] == "improving"]
    if len(improving_profiles) > 0:
        arjun_profile_id = improving_profiles.iloc[0]["profile_id"]

        for pdata in all_features:
            if pdata["profile_id"] == arjun_profile_id:
                features = np.array(pdata["features"], dtype=np.float32)
                features_scaled = scaler.transform(features.reshape(1, -1))[0]

                result = score_profile(features_scaled, xgb_model, ae_model, ae_error_threshold)
                pdata["pulse_score"] = result["pulse_score"]
                pdata["band"] = result["band"]
                pdata["shap"] = result["shap_top3"]

                demo_personas["arjun"] = {
                    "id": arjun_profile_id,
                    "name": "Arjun",
                    "archetype": "improving",
                    "age": 25,
                    "occupation": "Freelance Developer",
                    "city": "Pune",
                    "pulse_score": result["pulse_score"],
                    "band": result["band"],
                    "confidence": [result["confidence_interval"][0], result["confidence_interval"][1]],
                    "dimensions": pdata["dim_scores"],
                    "shap_top3": result["shap_top3"],
                }
                break

    print(f"✓ Generated {len(demo_personas)} demo personas:")
    for name, data in demo_personas.items():
        print(f"  - {data['name']}: {data['pulse_score']} ({data['band']})")

    return demo_personas


def main():
    """Main training pipeline"""
    backend_dir = Path(__file__).parent
    models_dir = backend_dir / "models"
    data_dir = backend_dir / "data"

    models_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}\n")

    # Step 1: Generate synthetic data
    print("=" * 60)
    print("STEP 1: Generating synthetic dataset...")
    print("=" * 60)
    profiles_df, transactions_df = generate_synthetic_dataset(
        output_path=str(data_dir / "synthetic_dataset.csv")
    )

    # Step 2: Compute features
    print("\n" + "=" * 60)
    print("STEP 2: Computing features...")
    print("=" * 60)
    X_scaled, y_normalized, y_original, profile_features, scaler = prepare_feature_matrix(
        transactions_df, profiles_df
    )

    # Step 3: Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_normalized, test_size=0.3, random_state=42
    )

    # Step 4: Train XGBoost
    print("\n" + "=" * 60)
    print("STEP 3: Training XGBoost...")
    print("=" * 60)
    xgb_model = train_xgboost(X_train, y_train)

    # Save XGBoost
    xgb_model.save_model(str(models_dir / "model.pkl"))
    print(f"✓ XGBoost saved to models/model.pkl")

    # Step 5: Train Autoencoder
    print("\n" + "=" * 60)
    print("STEP 4: Training PyTorch Autoencoder...")
    print("=" * 60)
    ae_model, ae_error_mean, ae_error_std = train_pytorch_ae(X_train, X_test, device=device)
    ae_error_threshold = ae_error_mean + 2 * ae_error_std

    # Save Autoencoder
    save_ae_model(ae_model, str(models_dir / "autoencoder.pt"))
    print(f"✓ Autoencoder saved to models/autoencoder.pt")

    # Save error threshold
    with open(models_dir / "ae_error_threshold.pkl", "wb") as f:
        pickle.dump({"mean": ae_error_mean, "std": ae_error_std, "threshold": ae_error_threshold}, f)

    # Step 6: Generate demo personas
    print("\n" + "=" * 60)
    print("STEP 5: Generating demo personas...")
    print("=" * 60)
    demo_personas = generate_demo_personas(
        profiles_df, transactions_df, xgb_model, ae_model, ae_error_threshold, scaler, profile_features, y_original
    )

    # Save demo personas
    with open(models_dir / "demo_personas.pkl", "wb") as f:
        pickle.dump(demo_personas, f)
    print(f"✓ Demo personas saved to models/demo_personas.pkl")

    # Save scaler
    with open(models_dir / "feature_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    print(f"✓ Feature scaler saved to models/feature_scaler.pkl")

    print("\n" + "=" * 60)
    print("✓ TRAINING COMPLETE!")
    print("=" * 60)
    print("\nArtifacts generated:")
    print("  - backend/models/model.pkl (XGBoost)")
    print("  - backend/models/autoencoder.pt (PyTorch AE)")
    print("  - backend/models/ae_error_threshold.pkl")
    print("  - backend/models/demo_personas.pkl")
    print("  - backend/models/feature_scaler.pkl")
    print("  - backend/data/synthetic_dataset.csv")


if __name__ == "__main__":
    main()
