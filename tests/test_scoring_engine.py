import copy
import json
from pathlib import Path

import pytest

from scoring_engine.scoring_engine import (
    _calculate_weighted_score,
    _load_weights,
    score,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_KEYS = {
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
    "null_count",
    "flags",
    "status",
}

VALID_STATUS = {"GO", "CAUTION", "DO_NOT_ENTER", "INSUFFICIENT_DATA", "REJECTED_DESERT"}

SCORE_KEYS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
)


def _load_mock_bundle():
    path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_1_full_mock_bundle_runs_without_error():
    bundle = copy.deepcopy(_load_mock_bundle())
    result = score(bundle)
    assert REQUIRED_KEYS == set(result.keys())
    assert result["status"] in VALID_STATUS


def test_2_null_metrics_reduce_confidence():
    bundle = copy.deepcopy(_load_mock_bundle())
    result = score(bundle)
    assert result["confidence_score"] < 100.0


def test_3_pop_total_none_rejected_desert():
    bundle = copy.deepcopy(_load_mock_bundle())
    bundle["demographic_data"]["pop_total"] = None
    result = score(bundle)
    assert result["status"] == "REJECTED_DESERT"
    assert result["confidence_score"] == 0.0


def test_4_pop_total_zero_rejected_desert():
    bundle = copy.deepcopy(_load_mock_bundle())
    bundle["demographic_data"]["pop_total"] = 0
    result = score(bundle)
    assert result["status"] == "REJECTED_DESERT"


def test_5_monopoly_flag_fires():
    bundle = copy.deepcopy(_load_mock_bundle())
    bundle["competitor_data"]["summary"]["top_3_review_share_pct"] = 65
    result = score(bundle)
    assert "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION" in result["flags"]


def test_6_zero_matching_competitors_flag_no_opportunity_override():
    """Zero Places matches: observational flag only; ordinary weighted opp/gap apply."""
    bundle = copy.deepcopy(_load_mock_bundle())
    bundle["competitor_data"]["summary"]["total_count"] = 0
    bundle["demographic_data"]["pop_total"] = 3000
    result = score(bundle)

    assert "NO_MATCHING_COMPETITORS_OBSERVED" in result["flags"]
    assert "GOLDMINE_ZERO_COMPETITORS" not in result["flags"]

    demand = result["demand_score"]
    pressure = result["competition_pressure_score"]
    assert demand is not None and pressure is not None

    weights = _load_weights()
    supply_proxy = 100.0 - float(pressure)
    expected_gap = _calculate_weighted_score(
        {"demand_proxy": demand, "supply_proxy": supply_proxy},
        weights["market_gap_score"],
    )
    expected_opp = _calculate_weighted_score(
        {
            "demand": demand,
            "market_gap": expected_gap,
            "competition_pressure_inverted": 100.0 - float(pressure),
        },
        weights["opportunity_score"],
    )
    assert expected_gap is not None and expected_opp is not None
    # Ordinary composition is authoritative — no Opportunity=100 / Gap≥85 override.
    assert result["market_gap_score"] == pytest.approx(expected_gap)
    assert result["opportunity_score"] == pytest.approx(expected_opp)


def test_7_data_desert_flag_fires():
    bundle = copy.deepcopy(_load_mock_bundle())
    bundle["demographic_data"]["median_household_income"] = None
    bundle["demographic_data"]["college_student_population_pct"] = None
    bundle["demographic_data"]["rent_to_income_ratio"] = None
    bundle["demographic_data"]["age_22_34_count"] = None
    result = score(bundle)
    assert "DATA_DESERT" in result["flags"]


def test_8_all_scores_clamped_zero_to_hundred():
    bundle = copy.deepcopy(_load_mock_bundle())
    result = score(bundle)
    for key in SCORE_KEYS:
        v = result[key]
        if v is not None:
            assert 0.0 <= float(v) <= 100.0
    assert 0.0 <= float(result["confidence_score"]) <= 100.0
