from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config.secrets import google_api_key
from data_layer.google_places import distance_miles, fetch_competitor_data


def _require_google_places_key() -> None:
    if not google_api_key():
        print("ERROR: Missing GOOGLE_PLACES_API_KEY or GOOGLE_API_KEY")
        sys.exit(1)


def _require_nonempty_env(var: str) -> str:
    v = os.getenv(var)
    if v is None or str(v).strip() == "":
        print(f"ERROR: Missing required env var: {var}")
        sys.exit(1)
    return str(v)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=repo_root / ".env")

    # 1) API key gate
    _require_google_places_key()

    # 2) DRY RUN gate (must exit BEFORE any Places HTTP)
    dry = str(os.getenv("DRY_RUN", "")).strip().lower()
    query_lat = float(_require_nonempty_env("QUERY_LAT"))
    query_lng = float(_require_nonempty_env("QUERY_LNG"))
    query_radius_miles = float(_require_nonempty_env("QUERY_RADIUS_MILES"))

    boston_lat = float(_require_nonempty_env("BOSTON_LAT"))
    boston_lng = float(_require_nonempty_env("BOSTON_LNG"))
    max_geofence_miles = float(_require_nonempty_env("MAX_GEOFENCE_MILES"))
    max_search_radius_miles = float(_require_nonempty_env("MAX_SEARCH_RADIUS_MILES"))

    distance_to_boston = distance_miles(query_lat, query_lng, boston_lat, boston_lng)
    if distance_to_boston > max_geofence_miles:
        print(
            "ERROR: Geofence check failed — query point is farther than MAX_GEOFENCE_MILES "
            f"from BOSTON_LAT/BOSTON_LNG ({distance_to_boston:.3f} mi > {max_geofence_miles} mi)."
        )
        sys.exit(1)

    if query_radius_miles > max_search_radius_miles:
        print(
            "ERROR: Radius check failed — query radius exceeds MAX_SEARCH_RADIUS_MILES "
            f"({query_radius_miles:.3f} mi > {max_search_radius_miles} mi)."
        )
        sys.exit(1)

    query = {
        "business_type": "coffee_shop",
        "location": "Boston University, Boston MA",
        "lat": query_lat,
        "lng": query_lng,
        "radius_miles": query_radius_miles,
        "target_customer": "students",
        "budget_level": "medium",
    }

    if dry == "true":
        print("[DRY_RUN] Validated query (no API requests will be made):")
        print(json.dumps(query, indent=2, sort_keys=False))
        return

    competitor_data = fetch_competitor_data(query)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = repo_root / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"bu_coffee_shop_processed_{ts}.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(competitor_data, f, indent=2)
        f.write("\n")

    summary = competitor_data.get("summary") or {}
    print("Summary")
    print(f"- Total competitors found: {summary.get('total_count')}")
    print(f"- Average rating: {summary.get('avg_rating')}")
    print(f"- top_3_review_share_pct: {summary.get('top_3_review_share_pct')}")
    print(f"- confidence_level: {competitor_data.get('confidence_level')}")
    print(f"- Output file path: {out_path}")


if __name__ == "__main__":
    main()
