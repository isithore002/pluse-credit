"""
ensemble.py - Blend XGBoost (60%) + Autoencoder (25%) + Heuristic Rules (15%)
Includes SHAP value computation for explainability
"""

import numpy as np
import xgboost as xgb
import shap
import torch
from typing import Dict, List, Tuple
import warnings

warnings.filterwarnings("ignore")


class EnsembleScorer:
    """Combine multiple models into final 300-850 score"""

    def __init__(
        self,
        xgb_model: xgb.Booster,
        ae_model=None,
        ae_error_threshold: float = 0.05,
    ):
        self.xgb_model = xgb_model
        self.ae_model = ae_model
        self.ae_error_threshold = ae_error_threshold

        # Ensemble weights
        self.xgb_weight = 0.60
        self.ae_weight = 0.25
        self.heuristic_weight = 0.15

    def score(
        self, raw_features: np.ndarray
    ) -> Tuple[int, int, int, Dict]:
        """
        Compute ensemble score and SHAP values
        Returns: (pulse_score, conf_low, conf_high, shap_dict)
        """
        # Normalize features to 0-1
        raw_features_norm = np.clip(raw_features, 0, 1)

        # Model 1: XGBoost (60%)
        xgb_features = xgb.DMatrix(raw_features_norm.reshape(1, -1))
        xgb_raw_score = float(self.xgb_model.predict(xgb_features)[0])
        xgb_score_normalized = np.clip(xgb_raw_score, 0, 1)

        # Model 2: Autoencoder (25%) - anomaly detection
        ae_score = 0.5  # Default if no AE model
        if self.ae_model is not None:
            try:
                ae_features_tensor = torch.from_numpy(raw_features_norm.reshape(1, -1)).float()
                with torch.no_grad():
                    ae_reconstructed, _ = self.ae_model(ae_features_tensor)
                ae_error = (ae_reconstructed - ae_features_tensor).pow(2).mean().item()
                ae_novelty = min(ae_error / self.ae_error_threshold, 1.0)
                ae_direction = 1 if xgb_score_normalized > 0.5 else -1
                ae_contribution = ae_novelty * ae_direction * 0.25
            except Exception as e:
                print(f"AE scoring error: {e}")
                ae_contribution = 0
        else:
            ae_contribution = 0

        # Model 3: Heuristic rules (15%)
        heuristic_score = self._compute_heuristic_score(raw_features)

        # Weighted ensemble
        raw_blend = (
            (xgb_score_normalized * self.xgb_weight)
            + ae_contribution
            + (heuristic_score * self.heuristic_weight)
        )

        # Platt scaling: map 0-1 to 300-850
        pulse_score = int(300 + (raw_blend * 550))
        pulse_score = max(300, min(850, pulse_score))

        # Confidence interval
        confidence_low = max(300, pulse_score - 30)
        confidence_high = min(850, pulse_score + 30)

        # SHAP values for explainability
        shap_dict = self._compute_shap_values(raw_features_norm)

        return pulse_score, confidence_low, confidence_high, shap_dict

    def _compute_heuristic_score(self, raw_features: np.ndarray) -> float:
        """
        Apply hard heuristic rules for credit risk
        Example: high outlier_count → lower score
        """
        # This is a simplified version - can be extended
        score = 0.5

        # Feature indices from feature_engine.py
        # F1: rhythm_cov (lower=better)
        rhythm_cov_idx = 0
        if len(raw_features) > rhythm_cov_idx:
            score += 0.1 * (1 - np.clip(raw_features[rhythm_cov_idx], 0, 1))

        # F19: outlier_count (lower=better)
        # Assuming outlier_count is around index 18
        outlier_idx = 18
        if len(raw_features) > outlier_idx:
            outlier_normalized = min(raw_features[outlier_idx] / 5, 1)
            score -= 0.1 * outlier_normalized

        return np.clip(score, 0, 1)

    def _compute_shap_values(self, raw_features: np.ndarray) -> Dict:
        """
        Compute SHAP values for top 3 features
        SHAP explains which features contributed most to the score
        """
        try:
            explainer = shap.TreeExplainer(self.xgb_model)
            shap_values = explainer.shap_values(raw_features.reshape(1, -1))

            # Get top 3 features by absolute SHAP value
            if len(shap_values.shape) > 1:
                shap_vals = shap_values[0]
            else:
                shap_vals = shap_values

            abs_shap = np.abs(shap_vals)
            top_3_indices = np.argsort(abs_shap)[-3:][::-1]

            feature_names = self._get_feature_names()
            shap_dict = {}

            for rank, idx in enumerate(top_3_indices, 1):
                if idx < len(feature_names):
                    shap_dict[f"feature_{rank}"] = {
                        "name": feature_names[idx],
                        "value": float(raw_features[idx]),
                        "impact": float(shap_vals[idx]),
                    }

            return shap_dict

        except Exception as e:
            print(f"SHAP computation error: {e}")
            return {}

    def _get_feature_names(self) -> List[str]:
        """Get human-readable feature names"""
        return [
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


def score_profile(
    raw_features: np.ndarray,
    xgb_model: xgb.Booster,
    ae_model=None,
    ae_error_threshold: float = 0.05,
) -> Dict:
    """
    Main scoring endpoint
    Input: raw_features array (24 features)
    Output: complete score dict with all components
    """
    scorer = EnsembleScorer(xgb_model, ae_model, ae_error_threshold)
    pulse_score, conf_low, conf_high, shap_dict = scorer.score(raw_features)

    # Determine band
    if pulse_score >= 750:
        band = "excellent"
    elif pulse_score >= 700:
        band = "very_good"
    elif pulse_score >= 650:
        band = "good"
    elif pulse_score >= 600:
        band = "fair"
    else:
        band = "poor"

    return {
        "pulse_score": pulse_score,
        "confidence_interval": [conf_low, conf_high],
        "band": band,
        "shap_top3": shap_dict,
    }


# Quick test
if __name__ == "__main__":
    # Dummy test
    test_features = np.random.randn(24)
    test_features = np.clip(test_features, 0, 1)

    # Create dummy XGBoost model
    X_dummy = np.random.randn(100, 24)
    y_dummy = np.random.uniform(0, 1, 100)
    dtrain = xgb.DMatrix(X_dummy, label=y_dummy)

    params = {
        "n_estimators": 100,
        "max_depth": 5,
        "learning_rate": 0.05,
        "objective": "reg:squarederror",
    }
    xgb_model = xgb.train(params, dtrain, num_boost_round=100)

    scorer = EnsembleScorer(xgb_model)
    result = score_profile(test_features, xgb_model)
    print(f"Test score result: {result}")
