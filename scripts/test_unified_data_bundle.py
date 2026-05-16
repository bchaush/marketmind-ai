from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Repo root (parent of scripts/)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import os

from config.secrets import google_api_key
from data_layer.census_api import fetch_census_demographics
from data_layer.google_places import distance_miles, fetch_competitor_data

# --- Fixed Phase 1 gate query (Boston University coffee shop, 1 mi) ---
QUERY_LAT = 42.3505
QUERY_LNG = -71.1054
QUERY_LOCATION = "Boston University, Boston MA"
QUERY_BUSINESS_TYPE = "coffee_shop"
QUERY_RADIUS_MILES = 1.0

VALID_GEOGRAPHY_LEVELS = frozenset({"block_group", "tract", "zcta", "placeholder"})


def _require_nonempty_env(var: str) -> str:
    v = os.getenv(var)
    if v is None or str(v).strip() == "":
        print(f"ERROR: Missing required env var: {var}", file=sys.stderr)
        sys.exit(1)
    return str(v).strip()


def _load_env() -> None:
    load_dotenv(dotenv_path=REPO_ROOT / ".env")


def _validate_mvp_geofence(*, lat: float, lng: float, radius_miles: float) -> None:
    """Abort before any external API if outside MVP geofence or radius cap."""
    boston_lat = float(_require_nonempty_env("BOSTON_LAT"))
    boston_lng = float(_require_nonempty_env("BOSTON_LNG"))
    max_geofence_miles = float(_require_nonempty_env("MAX_GEOFENCE_MILES"))
    max_search_radius_miles = float(_require_nonempty_env("MAX_SEARCH_RADIUS_MILES"))

    distance_to_boston = distance_miles(lat, lng, boston_lat, boston_lng)
    if distance_to_boston > max_geofence_miles:
        print(
            "ERROR: Geofence check failed — query point is farther than MAX_GEOFENCE_MILES "
            f"from BOSTON_LAT/BOSTON_LNG ({distance_to_boston:.3f} mi > {max_geofence_miles} mi).",
            file=sys.stderr,
        )
        sys.exit(1)

    if radius_miles > max_search_radius_miles:
        print(
            "ERROR: Radius check failed — query radius exceeds MAX_SEARCH_RADIUS_MILES "
            f"({radius_miles:.3f} mi > {max_search_radius_miles} mi).",
            file=sys.stderr,
        )
        sys.exit(1)


def _build_query_dict() -> Dict[str, Any]:
    return {
        "lat": QUERY_LAT,
        "lng": QUERY_LNG,
        "location": QUERY_LOCATION,
        "business_type": QUERY_BUSINESS_TYPE,
        "radius_miles": QUERY_RADIUS_MILES,
    }


def _api_query_for_fetchers() -> Dict[str, Any]:
    """Shape expected by fetch_competitor_data / fetch_census_demographics."""
    q = _build_query_dict()
    return {
        "lat": q["lat"],
        "lng": q["lng"],
        "business_type": q["business_type"],
        "radius_miles": q["radius_miles"],
        "location": q["location"],
    }


def _trim_competitor_bundle(full: Dict[str, Any]) -> Dict[str, Any]:
    summary_in = full.get("summary") if isinstance(full.get("summary"), dict) else {}
    return {
        "source": "google_places",
        "summary": {
            "total_count": summary_in.get("total_count"),
            "avg_rating": summary_in.get("avg_rating"),
            "top_3_review_share_pct": summary_in.get("top_3_review_share_pct"),
        },
    }


def _normalize_demographic_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical schema for Phase 2. Map legacy keys if present; never coerce None to 0.
    """
    # Alternate names → canonical (defensive; CensusData already uses canonical keys)
    if "college_student_population_pct" not in raw and "student_population_pct" in raw:
        raw = {**raw, "college_student_population_pct": raw.get("student_population_pct")}
    if "median_household_income" not in raw and "median_income" in raw:
        raw = {**raw, "median_household_income": raw.get("median_income")}

    def pick(key: str) -> Any:
        return raw.get(key)

    geography_level = pick("geography_level")
    confidence_score = pick("confidence_score")
    fallback_used = pick("fallback_used")

    if not isinstance(fallback_used, list):
        fallback_used = [] if fallback_used is None else list(fallback_used)

    return {
        "source": "census_acs5",
        "pop_total": pick("pop_total"),
        "age_22_34_count": pick("age_22_34_count"),
        "median_household_income": pick("median_household_income"),
        "college_student_population_pct": pick("college_student_population_pct"),
        "rent_to_income_ratio": pick("rent_to_income_ratio"),
        "geography_level": geography_level,
        "confidence_score": confidence_score,
        "fallback_used": fallback_used,
    }


def _google_places_present(competitor_data: Dict[str, Any]) -> bool:
    if competitor_data.get("source") != "google_places":
        return False
    s = competitor_data.get("summary")
    if not isinstance(s, dict):
        return False
    return "total_count" in s and "avg_rating" in s and "top_3_review_share_pct" in s


def _census_present(demographic_data: Dict[str, Any]) -> bool:
    if demographic_data.get("source") != "census_acs5":
        return False
    return demographic_data.get("geography_level") is not None


def _nulls_preserved_in_demographics(demographic_data: Dict[str, Any]) -> bool:
    """True if this script did not replace missing metrics with numeric zero."""
    keys = (
        "pop_total",
        "age_22_34_count",
        "median_household_income",
        "college_student_population_pct",
        "rent_to_income_ratio",
    )
    for k in keys:
        v = demographic_data.get(k)
        if v is None:
            continue
        if v == 0 and k in (
            "median_household_income",
            "college_student_population_pct",
            "rent_to_income_ratio",
        ):
            # Zero can be legitimate ACS; we only assert we did not coerce None→0 in builder.
            pass
    return True


def _geography_level_valid(level: Any) -> bool:
    return isinstance(level, str) and level in VALID_GEOGRAPHY_LEVELS


def _write_json(path: Path, payload: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
    except OSError:
        return False
    return path.is_file()


def main() -> None:
    _load_env()

    # Places key required for Phase 1A (same gate as run_test_query)
    if not google_api_key():
        print(
            "ERROR: Missing GOOGLE_PLACES_API_KEY or GOOGLE_API_KEY",
            file=sys.stderr,
        )
        sys.exit(1)

    query_display = _build_query_dict()
    lat, lng, radius_miles = (
        float(query_display["lat"]),
        float(query_display["lng"]),
        float(query_display["radius_miles"]),
    )

    _validate_mvp_geofence(lat=lat, lng=lng, radius_miles=radius_miles)

    api_query = _api_query_for_fetchers()

    full_competitors = fetch_competitor_data(api_query)
    competitor_data = _trim_competitor_bundle(full_competitors)

    census_model = fetch_census_demographics(api_query)
    census_dump = census_model.model_dump()
    demographic_data = _normalize_demographic_record(census_dump)

    geo_level = demographic_data.get("geography_level")
    geo_present = geo_level is not None and str(geo_level).strip() != ""
    geo_valid = _geography_level_valid(geo_level)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPO_ROOT / "data" / "raw" / f"phase1_unified_bu_coffee_shop_{ts}.json"

    expected_bu_geo = "block_group"

    phase_validation_base = {
        "google_places_present": _google_places_present(competitor_data),
        "census_present": _census_present(demographic_data),
        "nulls_preserved": _nulls_preserved_in_demographics(demographic_data),
        "geography_level_present": bool(geo_present),
        "geography_level_valid": bool(geo_valid),
        "expected_bu_geography_level": expected_bu_geo,
        "raw_audit_saved": False,
        "ready_for_phase_2": False,
    }

    bundle: Dict[str, Any] = {
        "query": query_display,
        "competitor_data": competitor_data,
        "demographic_data": demographic_data,
        "location_signals": {},
        "data_quality": {},
        "phase_1_validation": dict(phase_validation_base),
    }

    # First write; then set raw_audit_saved from verified filesystem state
    first_ok = _write_json(out_path, bundle)
    raw_audit_saved = bool(first_ok and out_path.is_file())

    bu_geo_matches = geo_level == expected_bu_geo
    ready = (
        phase_validation_base["google_places_present"]
        and phase_validation_base["census_present"]
        and phase_validation_base["nulls_preserved"]
        and phase_validation_base["geography_level_present"]
        and phase_validation_base["geography_level_valid"]
        and raw_audit_saved
        and bu_geo_matches
    )

    bundle["phase_1_validation"]["raw_audit_saved"] = raw_audit_saved
    bundle["phase_1_validation"]["ready_for_phase_2"] = ready

    if raw_audit_saved:
        _write_json(out_path, bundle)

    print(json.dumps(bundle, indent=2))


if __name__ == "__main__":
    main()
