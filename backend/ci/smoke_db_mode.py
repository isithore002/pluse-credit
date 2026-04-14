import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request


def _request_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url=url, method=method, data=data, headers=req_headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw) if raw else {}


def _supabase_count(base_url: str, api_key: str, table: str, query: str) -> int:
    url = f"{base_url.rstrip('/')}/rest/v1/{table}?{query}"
    status, rows = _request_json(
        url,
        method="GET",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept-Profile": "public",
            "Content-Profile": "public",
        },
    )
    if status != 200:
        raise RuntimeError(f"Supabase query failed for {table}: HTTP {status}")
    return len(rows)


def main() -> None:
    api_base = os.getenv("API_BASE", "http://127.0.0.1:8011")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for DB smoke test")

    profile_id = str(uuid.uuid4())
    transactions = [
        {
            "txn_date": "2024-01-01",
            "amount": 50.0,
            "direction": "DR",
            "vpa": "zomato@upi",
            "merchant_name": "Zomato",
            "category": "food",
            "remarks": "canteen lunch",
        },
        {
            "txn_date": "2024-01-02",
            "amount": 60.0,
            "direction": "DR",
            "vpa": "swiggy@upi",
            "merchant_name": "Swiggy",
            "category": "food",
            "remarks": "food order",
        },
        {
            "txn_date": "2024-01-03",
            "amount": 5000.0,
            "direction": "CR",
            "vpa": "parent@upi",
            "merchant_name": "Parent Transfer",
            "category": "income",
            "remarks": "stipend",
        },
        {
            "txn_date": "2024-01-05",
            "amount": 6000.0,
            "direction": "DR",
            "vpa": "landlord@upi",
            "merchant_name": "Landlord",
            "category": "rent",
            "remarks": "monthly rent",
        },
        {
            "txn_date": "2024-01-08",
            "amount": 200.0,
            "direction": "DR",
            "vpa": "uber@upi",
            "merchant_name": "Uber",
            "category": "transport",
            "remarks": "ride",
        },
    ]

    score_status, score_json = _request_json(
        f"{api_base}/api/score",
        method="POST",
        body={"profile_id": profile_id, "transactions": transactions},
    )
    if score_status != 200:
        raise RuntimeError(f"/api/score failed with HTTP {score_status}")

    if score_json.get("profile_id") != profile_id:
        raise RuntimeError("/api/score response profile_id mismatch")

    simulate_status, simulate_json = _request_json(
        f"{api_base}/api/simulate",
        method="POST",
        body={"base_profile_id": profile_id, "overrides": {"rhythm": 80}},
    )
    if simulate_status != 200:
        raise RuntimeError(f"/api/simulate failed with HTTP {simulate_status}")

    if simulate_json.get("profile_id") != profile_id:
        raise RuntimeError("/api/simulate did not return expected DB-backed profile")

    checks = [
        ("profiles", f"id=eq.{profile_id}&select=id"),
        ("transactions", f"profile_id=eq.{profile_id}&select=id"),
        ("feature_vectors", f"profile_id=eq.{profile_id}&select=id"),
        ("scores", f"profile_id=eq.{profile_id}&select=id"),
    ]

    for table, query in checks:
        count = _supabase_count(supabase_url, supabase_service_key, table, query)
        if count < 1:
            raise RuntimeError(f"No persisted rows found in table '{table}' for profile {profile_id}")

    print(f"SMOKE_OK profile={profile_id} score={score_json.get('pulse_score')}")


if __name__ == "__main__":
    main()
