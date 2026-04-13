"""
synthetic_data.py - Generates 1,000 synthetic profiles with realistic UPI transaction patterns
Used for training XGBoost and PyTorch autoencoder models before handling real data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple

# Fixed random seed for reproducibility
np.random.seed(42)

# Configuration for each archetype
ARCHETYPES = {
    "disciplined_student": {
        "n": 300,
        "rhythm_cov_range": (0.1, 0.25),
        "monthly_spend_range": (3000, 8000),
        "merchant_hhi_range": (0.4, 0.7),
        "unique_senders_range": (3, 12),
        "label_range": (650, 820),
    },
    "erratic_gig_worker": {
        "n": 250,
        "rhythm_cov_range": (0.4, 0.8),
        "monthly_spend_range": (8000, 25000),
        "merchant_hhi_range": (0.1, 0.35),
        "unique_senders_range": (1, 5),
        "label_range": (400, 620),
    },
    "improving": {
        "n": 250,
        "rhythm_cov_trend": "decreasing",
        "label_range": (580, 720),
    },
    "defaulted": {
        "n": 200,
        "rhythm_cov_range": (0.6, 1.2),
        "label_range": (300, 480),
    },
}

MERCHANTS = {
    "food": {
        "names": ["Zomato", "Swiggy", "Blinkit", "Dunzo"],
        "vpas": ["zomato@upi", "swiggy@upi", "blinkit@upi", "dunzo@upi"],
    },
    "transport": {
        "names": ["Uber", "Ola", "Rapido", "Namma Yatri"],
        "vpas": ["uber@upi", "ola@upi", "rapido@upi", "nammayatri@upi"],
    },
    "shopping": {
        "names": ["Amazon", "Flipkart", "Myntra", "Ajio"],
        "vpas": ["amazon@upi", "flipkart@upi", "myntra@upi", "ajio@upi"],
    },
    "utilities": {
        "names": ["Bill Pay", "Airtel", "Jio", "BSNL"],
        "vpas": ["bill@upi", "airtel@upi", "jio@upi", "bsnl@upi"],
    },
    "rent": {
        "names": ["Landlord", "PG Admin", "Hostel Fee"],
        "vpas": ["landlord@upi", "pgadmin@upi", "hostelfee@upi"],
    },
}

CONTACT_NAMES = [
    f"contact_{i}@upi" for i in range(100)
]  # Generic contact VPAs


def generate_transactions_for_archetype(
    profile_id: str, archetype: str, archetype_params: Dict
) -> List[Dict]:
    """Generate 90 days of transactions for a single profile"""
    transactions = []
    start_date = datetime(2023, 12, 1)
    end_date = start_date + timedelta(days=90)

    if archetype == "disciplined_student":
        # Daily small payments + weekly bigger ones
        current_date = start_date
        while current_date < end_date:
            # Daily canteen spend (₹40-60)
            if np.random.random() > 0.1:
                amount = np.random.uniform(40, 60)
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": round(amount, 2),
                    "direction": "DR",
                    "vpa": np.random.choice(MERCHANTS["food"]["vpas"]),
                    "merchant_name": np.random.choice(MERCHANTS["food"]["names"]),
                    "category": "food",
                    "remarks": f"Daily canteen",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}",
                })

            # Weekly transport
            if current_date.weekday() == 0:  # Monday
                amount = np.random.uniform(150, 250)
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": round(amount, 2),
                    "direction": "DR",
                    "vpa": np.random.choice(MERCHANTS["transport"]["vpas"]),
                    "merchant_name": np.random.choice(MERCHANTS["transport"]["names"]),
                    "category": "transport",
                    "remarks": f"Weekly transport",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_w",
                })

            # Monthly rent on 5th
            if current_date.day == 5:
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": 6000.0,
                    "direction": "DR",
                    "vpa": np.random.choice(MERCHANTS["rent"]["vpas"]),
                    "merchant_name": MERCHANTS["rent"]["names"][0],
                    "category": "rent",
                    "remarks": f"Monthly rent",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_r",
                })

            # Occasional incoming transfers (stipend)
            if current_date.day == 1 and np.random.random() > 0.5:
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": np.random.uniform(5000, 10000),
                    "direction": "CR",
                    "vpa": "parent@upi",
                    "merchant_name": "Parent Transfer",
                    "category": "income",
                    "remarks": f"Monthly stipend",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_in",
                })

            current_date += timedelta(days=1)

    elif archetype == "erratic_gig_worker":
        # Irregular earnings + high spending
        current_date = start_date
        while current_date < end_date:
            # Irregular income (3-4 times per week)
            if np.random.random() > 0.6:
                amount = np.random.uniform(500, 2000)
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": round(amount, 2),
                    "direction": "CR",
                    "vpa": "swiggy_earnings@upi",
                    "merchant_name": "Swiggy Earnings",
                    "category": "income",
                    "remarks": f"Delivery earnings",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_e",
                })

            # High fuel spend
            if np.random.random() > 0.85:
                amount = np.random.uniform(300, 800)
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": round(amount, 2),
                    "direction": "DR",
                    "vpa": "fuel@upi",
                    "merchant_name": "Fuel Station",
                    "category": "transport",
                    "remarks": f"Bike fuel",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_f",
                })

            # Food spending (erratic)
            if np.random.random() > 0.3:
                amount = np.random.uniform(100, 600)
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": round(amount, 2),
                    "direction": "DR",
                    "vpa": np.random.choice(MERCHANTS["food"]["vpas"]),
                    "merchant_name": np.random.choice(MERCHANTS["food"]["names"]),
                    "category": "food",
                    "remarks": f"Food delivery",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_d",
                })

            current_date += timedelta(days=1)

    elif archetype == "improving":
        # Pattern gets more regular over time
        current_date = start_date
        month_count = 0
        while current_date < end_date:
            month_count = (current_date.day - 1) // 30

            # Rhythm improves over months
            regularity = 0.4 + (month_count * 0.2)  # 0.4 → 0.6 → 0.8

            if np.random.random() > (1 - regularity):
                amount = np.random.uniform(50, 150)
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": round(amount, 2),
                    "direction": "DR",
                    "vpa": np.random.choice(MERCHANTS["food"]["vpas"]),
                    "merchant_name": np.random.choice(MERCHANTS["food"]["names"]),
                    "category": "food",
                    "remarks": f"Food",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}",
                })

            # Fixed rent payment after month 1
            if month_count >= 1 and current_date.day == 15:
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": 5000.0,
                    "direction": "DR",
                    "vpa": "landlord@upi",
                    "merchant_name": "Rent",
                    "category": "rent",
                    "remarks": f"Fixed rent",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_r",
                })

            # Monthly stipend
            if current_date.day == 1:
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": np.random.uniform(3000, 7000),
                    "direction": "CR",
                    "vpa": "income@upi",
                    "merchant_name": "Monthly Income",
                    "category": "income",
                    "remarks": f"Freelance income",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_in",
                })

            current_date += timedelta(days=1)

    elif archetype == "defaulted":
        # Erratic, high-risk patterns
        current_date = start_date
        while current_date < end_date:
            # Inconsistent spending
            if np.random.random() > 0.2:
                amount = np.random.uniform(500, 3000)
                if np.random.random() > 0.5:
                    transactions.append({
                        "profile_id": profile_id,
                        "txn_date": current_date.date(),
                        "amount": round(amount, 2),
                        "direction": "DR",
                        "vpa": "unknown@upi",
                        "merchant_name": "Unknown",
                        "category": "other",
                        "remarks": f"Transfer",
                        "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}",
                    })

            # Almost no regular income
            if current_date.day == 1 and np.random.random() > 0.8:
                transactions.append({
                    "profile_id": profile_id,
                    "txn_date": current_date.date(),
                    "amount": np.random.uniform(1000, 3000),
                    "direction": "CR",
                    "vpa": "sporadic@upi",
                    "merchant_name": "Sporadic",
                    "category": "income",
                    "remarks": f"Occasional",
                    "utr": f"UTR{profile_id[:8]}{current_date.strftime('%Y%m%d')}_in",
                })

            current_date += timedelta(days=1)

    return transactions


def generate_synthetic_dataset(output_path: str = "backend/data/synthetic_dataset.csv"):
    """
    Generate 1,000 synthetic profiles with transactions and ground-truth labels
    """
    all_profiles = []
    all_transactions = []
    profile_counter = 0

    for archetype, config in ARCHETYPES.items():
        n_profiles = config["n"]
        for i in range(n_profiles):
            profile_id = f"{archetype}_{profile_counter:04d}"
            profile_counter += 1

            # Assign score label from range
            score_label = np.random.randint(
                config["label_range"][0], config["label_range"][1]
            )

            all_profiles.append({
                "profile_id": profile_id,
                "archetype": archetype,
                "pulse_score": score_label,
            })

            # Generate transactions
            txns = generate_transactions_for_archetype(profile_id, archetype, config)
            all_transactions.extend(txns)

    # Convert to DataFrames
    profiles_df = pd.DataFrame(all_profiles)
    transactions_df = pd.DataFrame(all_transactions)

    # Save transactions to CSV
    transactions_df.to_csv(output_path, index=False)
    print(f"✓ Synthetic dataset saved: {output_path}")
    print(
        f"  - {len(profiles_df)} profiles across {profiles_df['archetype'].nunique()} archetypes"
    )
    print(f"  - {len(transactions_df)} transactions")
    print(f"  - Score range: {profiles_df['pulse_score'].min()}-{profiles_df['pulse_score'].max()}")

    return profiles_df, transactions_df


if __name__ == "__main__":
    profiles_df, transactions_df = generate_synthetic_dataset()
    print(f"\nProfile summary:\n{profiles_df.groupby('archetype').agg({'pulse_score': ['count', 'mean', 'min', 'max']})}")
