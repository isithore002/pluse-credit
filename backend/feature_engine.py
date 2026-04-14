"""
feature_engine.py - Computes all 24 features and 6 behavioral dimensions
This is the core of the ML pipeline - all models depend on these features
"""

import pandas as pd
import numpy as np
import networkx as nx
from scipy.fft import fft
from scipy.stats import entropy, zscore
from typing import Dict, List, Tuple, Any
import warnings

warnings.filterwarnings("ignore")


class FeatureEngine:
    """Compute 24 raw features organized into 6 behavioral dimensions"""

    def __init__(self):
        self.dimensions = [
            "rhythm",
            "merchant",
            "social",
            "calendar",
            "velocity",
            "nlp",
        ]

    def compute_all_features(
        self, transactions_df: pd.DataFrame, profile_id: str
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Compute all 24 features and 6 dimension scores
        Returns: (raw_features_dict, dimension_scores_dict)
        """
        raw_features = {}
        dimension_scores = {}

        try:
            # Dimension 1: Payment Rhythm (4 features)
            rhythm_features = self._compute_rhythm_features(transactions_df)
            raw_features.update({f"rhythm_{k}": v for k, v in rhythm_features.items()})

            # Dimension 2: Merchant Consistency (4 features)
            merchant_features = self._compute_merchant_features(transactions_df)
            raw_features.update({f"merchant_{k}": v for k, v in merchant_features.items()})

            # Dimension 3: Social Trust Graph (4 features)
            social_features = self._compute_social_features(transactions_df)
            raw_features.update({f"social_{k}": v for k, v in social_features.items()})

            # Dimension 4: Calendar Alignment (4 features)
            calendar_features = self._compute_calendar_features(transactions_df)
            raw_features.update({f"calendar_{k}": v for k, v in calendar_features.items()})

            # Dimension 5: Velocity Stability (4 features)
            velocity_features = self._compute_velocity_features(transactions_df)
            raw_features.update({f"velocity_{k}": v for k, v in velocity_features.items()})

            # Dimension 6: NLP Intent Score (4 features)
            nlp_features = self._compute_nlp_features(transactions_df)
            raw_features.update({f"nlp_{k}": v for k, v in nlp_features.items()})

            # Normalize each dimension to 0-100 scale
            dimension_scores["rhythm"] = self._normalize_dimension(rhythm_features)
            dimension_scores["merchant"] = self._normalize_dimension(merchant_features)
            dimension_scores["social"] = self._normalize_dimension(social_features)
            dimension_scores["calendar"] = self._normalize_dimension(calendar_features)
            dimension_scores["velocity"] = self._normalize_dimension(velocity_features)
            dimension_scores["nlp"] = self._normalize_dimension(nlp_features)

        except Exception as e:
            print(f"Error computing features for {profile_id}: {e}")
            return self._get_default_features()

        return raw_features, dimension_scores

    def _compute_rhythm_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """F1-F4: Payment regularity patterns"""
        features = {}

        # F1: Coefficient of Variation of inter-transaction gaps
        dr_dates = df[df["direction"] == "DR"]["txn_date"].sort_values()
        if len(dr_dates) > 1:
            gaps = dr_dates.diff().dt.days.dropna()
            if len(gaps) > 0 and gaps.mean() > 0:
                features["cov"] = gaps.std() / gaps.mean()  # lower = more regular
            else:
                features["cov"] = 1.0
        else:
            features["cov"] = 1.0

        # F2: Longest consecutive-day streak with at least one DR transaction
        dr_dates = (
            pd.to_datetime(df[df["direction"] == "DR"]["txn_date"], errors="coerce")
            .dropna()
            .dt.normalize()
            .sort_values()
            .unique()
        )
        max_streak = 0
        current_streak = 0
        if len(dr_dates) > 0:
            dr_dates_set = {pd.Timestamp(d) for d in dr_dates}
            for date in pd.date_range(start=dr_dates[0], end=dr_dates[-1], freq="D"):
                if date in dr_dates_set:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 0
        features["streak"] = max_streak

        # F3: Rolling 7-day / 30-day transaction count ratio (recency)
        date_range = pd.date_range(start=df["txn_date"].min(), end=df["txn_date"].max())
        daily_counts = df.groupby("txn_date").size().reindex(date_range, fill_value=0)
        last_7_days = daily_counts.iloc[-7:].sum() if len(daily_counts) >= 7 else daily_counts.sum()
        last_30_days = daily_counts.iloc[-30:].sum() if len(daily_counts) >= 30 else daily_counts.sum()
        features["recency_ratio"] = last_7_days / max(last_30_days, 1)

        # F4: FFT-based weekly seasonality index
        if len(daily_counts) >= 14:
            fft_vals = np.abs(fft(daily_counts.values))
            # Power at weekly frequency (every 7th element)
            weekly_idx = len(fft_vals) // 7
            features["weekly_fft"] = float(fft_vals[weekly_idx]) if weekly_idx < len(fft_vals) else 0.0
        else:
            features["weekly_fft"] = 0.0

        return features

    def _compute_merchant_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """F5-F8: Lifestyle stability and merchant consistency"""
        features = {}

        # F5: Herfindahl-Hirschman Index (HHI) on merchant spend share
        merchant_spend = df[df["direction"] == "DR"].groupby("merchant_name")["amount"].sum()
        total_spend = merchant_spend.sum()
        if total_spend > 0:
            shares = merchant_spend / total_spend
            features["hhi"] = float((shares ** 2).sum())
        else:
            features["hhi"] = 0.0

        # F6: Top-5 merchant retention across months
        df["month"] = df["txn_date"].dt.to_period("M")
        months = df["month"].unique()
        if len(months) >= 3:
            top_merchants_by_month = []
            for month in months:
                month_data = df[df["month"] == month]
                top_5 = month_data[month_data["direction"] == "DR"].groupby("merchant_name")["amount"].sum().nlargest(5)
                top_merchants_by_month.append(set(top_5.index))

            intersection = set.intersection(*top_merchants_by_month)
            features["retention"] = len(intersection) / max(len(top_merchants_by_month[0]), 1)
        else:
            features["retention"] = 0.0

        # F7: Category entropy (lower = more stable lifestyle)
        category_dist = df[df["direction"] == "DR"]["category"].value_counts(normalize=True)
        if len(category_dist) > 0:
            features["entropy"] = float(entropy(category_dist))
        else:
            features["entropy"] = 0.0

        # F8: Recurring merchant count (merchants in ALL months)
        if len(months) >= 2:
            all_merchants = df[df["direction"] == "DR"]["merchant_name"].unique()
            recurring = 0
            for merchant in all_merchants:
                merchant_months = df[df["merchant_name"] == merchant]["month"].nunique()
                if merchant_months == len(months):
                    recurring += 1
            features["recurring"] = recurring
        else:
            features["recurring"] = 0

        return features

    def _compute_social_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """F9-F12: Social trust and network analysis via NetworkX"""
        features = {}

        # Build directed graph
        G = nx.DiGraph()
        for _, row in df.iterrows():
            if row["direction"] == "DR":
                G.add_edge("USER", row["vpa"], weight=row["amount"])
            else:
                G.add_edge(row["vpa"], "USER", weight=row["amount"])

        # F9: Unique inbound VPA count
        unique_senders = len(list(G.predecessors("USER")))
        features["unique_senders"] = unique_senders

        # F10: Inbound-to-outbound sender ratio
        unique_receivers = len(list(G.successors("USER")))
        features["sender_ratio"] = unique_senders / max(unique_receivers, 1)

        # F11: Reciprocity score
        senders = set(G.predecessors("USER"))
        receivers = set(G.successors("USER"))
        reciprocal_count = len(senders.intersection(receivers))
        features["reciprocity"] = reciprocal_count / max(len(senders.union(receivers)), 1)

        # F12: User degree centrality
        if len(G) > 1:
            centrality = nx.degree_centrality(G).get("USER", 0)
        else:
            centrality = 0.0
        features["centrality"] = centrality

        return features

    def _compute_calendar_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """F13-F16: Temporal patterns (semester, stipend, rent, festivals)"""
        features = {}
        SEMESTER_MONTHS = [1, 2, 7, 8]
        INDIAN_FESTIVALS = {
            "diwali": [11, 1],
            "holi": [3],
            "eid": [4, 5],
            "navratri": [10],
        }

        # F13: Semester boundary detection
        semester_months_present = df[df["txn_date"].dt.month.isin(SEMESTER_MONTHS)].groupby(df["txn_date"].dt.month).size()
        features["semester_score"] = len(semester_months_present) / len(SEMESTER_MONTHS)

        # F14: Stipend fingerprint (fixed income on same day each month)
        large_cr = df[(df["direction"] == "CR") & (df["amount"] > 2000)]
        if len(large_cr) > 0:
            monthly_days = large_cr.groupby(large_cr["txn_date"].dt.month)["txn_date"].apply(lambda x: x.dt.day.mode()[0] if len(x.dt.day.mode()) > 0 else x.dt.day.mean())
            day_std = monthly_days.std() if len(monthly_days) > 1 else 0
            features["stipend_regularity"] = 1 / (1 + day_std)
        else:
            features["stipend_regularity"] = 0.0

        # F15: Rent regularity
        rent_keywords = ["rent", "room", "pg", "hostel"]
        rent_txns = df[df["remarks"].str.lower().str.contains("|".join(rent_keywords), na=False)]
        if len(rent_txns) > 0:
            rent_dates = rent_txns["txn_date"].dt.day
            if len(rent_dates) > 1:
                features["rent_regularity"] = 1 / (1 + rent_dates.std())
            else:
                features["rent_regularity"] = 1.0
        else:
            features["rent_regularity"] = 0.0

        # F16: Festival spike normalization (mark transactions within 5 days of festivals)
        festival_adjusted = 0.5  # placeholder
        features["festival_adjusted"] = festival_adjusted

        return features

    def _compute_velocity_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """F17-F20: Spend volatility and anomaly detection"""
        features = {}

        # F17: Rolling 30-day spend Z-score
        dr_df = df[df["direction"] == "DR"].copy()
        dr_df["month"] = dr_df["txn_date"].dt.to_period("M")
        monthly_spend = dr_df.groupby("month")["amount"].sum()

        if len(monthly_spend) > 1:
            try:
                z_scores = np.abs(zscore(monthly_spend))
                features["zscore"] = float(z_scores.mean())
            except:
                features["zscore"] = 0.0
        else:
            features["zscore"] = 0.0

        # F18: Month-over-month spend delta
        if len(monthly_spend) > 1:
            mom_changes = monthly_spend.pct_change().abs().dropna()
            features["mom_delta"] = float(mom_changes.mean())
        else:
            features["mom_delta"] = 0.0

        # F19: Outlier transaction count
        mean_dr = dr_df["amount"].mean()
        std_dr = dr_df["amount"].std()
        outlier_count = len(dr_df[dr_df["amount"] > mean_dr + 3 * std_dr])
        features["outlier_count"] = float(outlier_count)

        # F20: Micro-splitting detection
        daily_vpa = df[df["direction"] == "DR"].groupby(["txn_date", "vpa"]).size()
        micro_split = len(daily_vpa[daily_vpa >= 3])
        features["micro_split"] = float(micro_split)

        return features

    def _compute_nlp_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """F21-F24: NLP-based intent classification"""
        features = {}

        PRODUCTIVE_KEYWORDS = [
            "fees",
            "tuition",
            "rent",
            "hostel",
            "medicine",
            "hospital",
            "books",
            "stationery",
            "insurance",
            "emi",
            "loan",
        ]
        IMPULSIVE_KEYWORDS = ["party", "pub", "casino", "bet", "gaming", "recharge"]

        remarks_text = " ".join(df["remarks"].dropna().astype(str)).lower()

        # F21: Productive keyword ratio
        productive_hits = sum(remarks_text.count(kw) for kw in PRODUCTIVE_KEYWORDS)
        impulsive_hits = sum(remarks_text.count(kw) for kw in IMPULSIVE_KEYWORDS)
        total_hits = productive_hits + impulsive_hits
        features["productive_ratio"] = productive_hits / max(total_hits, 1)

        # F22: Organization density (named entity count)
        # Simplified: count capitalized words as proxy for entities
        words = remarks_text.split()
        org_count = sum(1 for w in words if w[0].isupper() if len(w) > 0)
        features["org_density"] = org_count / max(len(words), 1)

        # F23: Gemini intent classification (placeholder for now)
        # Will be computed asynchronously in real pipeline
        features["gemini_intent"] = 0.5

        # F24: Average remark length
        remark_lengths = df["remarks"].dropna().str.len()
        if len(remark_lengths) > 0:
            features["remark_richness"] = min(remark_lengths.mean() / 50, 1.0)
        else:
            features["remark_richness"] = 0.0

        return features

    def _normalize_dimension(self, features_dict: Dict[str, float]) -> float:
        """Normalize dimension features to 0-100 scale"""
        if not features_dict:
            return 50.0

        values = list(features_dict.values())
        values = [v for v in values if not np.isnan(v) and not np.isinf(v)]

        if not values:
            return 50.0

        # Simple scaling: average of clipped 0-1 values, then scale to 0-100
        normalized = np.mean([min(max(v, 0), 1) for v in values])
        return float(normalized * 100)

    def _get_default_features(self) -> Tuple[Dict, Dict]:
        """Return default features for error handling"""
        raw_features = {f"rhythm_cov": 0.5, f"rhythm_streak": 0, f"rhythm_recency_ratio": 0.5, f"rhythm_weekly_fft": 0,
                       f"merchant_hhi": 0.3, f"merchant_retention": 0.5, f"merchant_entropy": 1.0, f"merchant_recurring": 0,
                       f"social_unique_senders": 0, f"social_sender_ratio": 0.5, f"social_reciprocity": 0, f"social_centrality": 0,
                       f"calendar_semester_score": 0.5, f"calendar_stipend_regularity": 0.5, f"calendar_rent_regularity": 0, f"calendar_festival_adjusted": 0.5,
                       f"velocity_zscore": 0.5, f"velocity_mom_delta": 0.5, f"velocity_outlier_count": 0, f"velocity_micro_split": 0,
                       f"nlp_productive_ratio": 0.5, f"nlp_org_density": 0.2, f"nlp_gemini_intent": 0.5, f"nlp_remark_richness": 0.3}

        dimension_scores = {dim: 50.0 for dim in self.dimensions}

        return raw_features, dimension_scores


# Quick test
if __name__ == "__main__":
    from synthetic_data import generate_synthetic_dataset

    profiles_df, transactions_df = generate_synthetic_dataset()

    engine = FeatureEngine()

    # Test on first profile
    profile_id = transactions_df["profile_id"].iloc[0]
    profile_txns = transactions_df[transactions_df["profile_id"] == profile_id].copy()
    profile_txns["txn_date"] = pd.to_datetime(profile_txns["txn_date"])

    raw_features, dim_scores = engine.compute_all_features(profile_txns, profile_id)

    print(f"Profile: {profile_id}")
    print(f"Dimension Scores: {dim_scores}")
    print(f"Sample Raw Features: {list(raw_features.items())[:5]}")
