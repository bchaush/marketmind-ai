from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from pipeline import fetch_live_bundle
from pipeline.cache import CACHE_DIR, make_cache_key
from scoring_engine.scoring_engine import score

SCORE_KEYS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
)

MOCK_GOLDEN = {
    "demand_score": 65.40,
    "competition_pressure_score": 51.08,
    "market_gap_score": 60.46,
    "risk_score": 58.70,
    "opportunity_score": 60.38,
    "confidence_score": 74.0,
}


def _phase2_to_payload(phase2: dict):
    scores = {k: phase2[k] for k in SCORE_KEYS}
    flags = list(phase2["flags"])
    raw = build_analyst_payload(scores, flags)
    return scores, validate_analyst_payload(raw)


def main() -> None:
    print("=" * 60)
    print("Phase 5 Live Pipeline Smoke Test")
    print("=" * 60)

    # --- Scenario 1: BU Golden Path (Cold + Hot) ---
    print("\n--- Scenario 1: BU Golden Path (Cold + Hot) ---")
    lat_s1, lng_s1 = 42.3505, -71.1054
    biz = "coffee_shop"
    rad = 1.0

    cache_key = make_cache_key(lat_s1, lng_s1, biz, rad)
    cache_path = CACHE_DIR / f"{cache_key}.json"
    print(f"Cache key: {cache_key}")
    print(f"Cache file path: {cache_path}")

    if cache_path.is_file():
        try:
            cache_path.unlink()
            print("Removed existing cache file (cold start guaranteed).")
        except OSError as exc:
            print(f"WARN: could not delete cache file: {exc}")

    print("\nRun 1 (Cold)")
    try:
        bundle1 = fetch_live_bundle(lat_s1, lng_s1, biz, radius_miles=rad)
        phase2_1 = score(bundle1)
        scores1, payload1 = _phase2_to_payload(phase2_1)
        print("Scores (Run 1):")
        for k in SCORE_KEYS:
            print(f"  {k}: {scores1[k]}")
        print("\nDelta vs mock golden (Run 1):")
        for k in SCORE_KEYS:
            actual = scores1[k]
            golden = MOCK_GOLDEN[k]
            if actual is None:
                print(f"  {k}: actual=None  golden={golden}  delta=n/a")
            else:
                delta = float(actual) - golden
                print(f"  {k}: actual={actual}  golden={golden}  delta={delta:+.4f}")
        status1 = payload1.executive_decision.final_status
    except Exception as exc:
        print(f"Scenario 1 Run 1 FAILED: {type(exc).__name__}: {exc}")
        status1 = None

    print("\nRun 2 (Hot)")
    cache_exists = cache_path.is_file()
    print(f"Cache file exists before hot fetch: {'yes' if cache_exists else 'no'}")

    try:
        bundle2 = fetch_live_bundle(lat_s1, lng_s1, biz, radius_miles=rad)
        phase2_2 = score(bundle2)
        _, payload2 = _phase2_to_payload(phase2_2)
        status2 = payload2.executive_decision.final_status
    except Exception as exc:
        print(f"Scenario 1 Run 2 FAILED: {type(exc).__name__}: {exc}")
        status2 = None

    cache_exists_after = cache_path.is_file()
    print(f"Cache file exists after hot run: {'PASS' if cache_exists_after else 'FAIL'} ({cache_path})")

    if status1 is not None and status2 is not None:
        idem = status1 == status2
        print(f"IDEMPOTENCY (final_status Run1 == Run2): {'PASS' if idem else 'FAIL'}  ({status1!r} vs {status2!r})")
    else:
        print("IDEMPOTENCY: FAIL (missing payload from one run)")

    # --- Scenario 2: Geofence Rejection ---
    print("\n--- Scenario 2: Geofence Rejection (Providence, RI) ---")
    try:
        fetch_live_bundle(41.8240, -71.4128, biz, radius_miles=1.0)
        print("GEOFENCE: FAIL (expected ValueError, none raised)")
    except ValueError as exc:
        print(f"GEOFENCE: PASS (ValueError: {exc})")
    except Exception as exc:
        print(f"GEOFENCE: FAIL (expected ValueError, got {type(exc).__name__}: {exc})")

    # --- Scenario 3: Data Desert / thin Census (Inman Square) ---
    print("\n--- Scenario 3: Data Desert Degraded Path (Inman Square) ---")
    try:
        bundle3 = fetch_live_bundle(42.3736, -71.1097, biz, radius_miles=1.0)
        phase2_3 = score(bundle3)
        scores3, payload3 = _phase2_to_payload(phase2_3)
        fs = payload3.executive_decision.final_status
        conf = scores3.get("confidence_score")
        flags = list(phase2_3["flags"])
        has_desert = "DATA_DESERT" in flags
        print(f"final_status: {fs}")
        print(f"confidence_score: {conf}")
        print(f"DATA_DESERT in phase2 flags: {has_desert}")
    except Exception as exc:
        print(f"Scenario 3 FAILED: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print("Smoke test complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
