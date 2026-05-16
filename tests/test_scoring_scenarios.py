import copy
import json
from pathlib import Path

import pytest

from scoring_engine.scoring_engine import score


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_base_bundle():
    path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_golden_bu_snapshot():
    bundle = copy.deepcopy(_load_base_bundle())
    result = score(bundle)
    assert result["demand_score"] == pytest.approx(65.40467266412789, rel=1e-4)
    assert result["competition_pressure_score"] == pytest.approx(51.07999999999999, rel=1e-4)
    assert result["market_gap_score"] == pytest.approx(60.45927086488952, rel=1e-4)
    assert result["risk_score"] == pytest.approx(58.69999999999999, rel=1e-4)
    assert result["opportunity_score"] == pytest.approx(60.37684750156889, rel=1e-4)
    assert result["confidence_score"] == pytest.approx(74.0, rel=1e-4)
    assert result["null_count"] == 3
    assert result["flags"] == ["DATA_DESERT"]
    assert result["status"] == "CAUTION"


def test_monotonicity_demand_increases_with_population():
    b_low = copy.deepcopy(_load_base_bundle())
    b_low["demographic_data"]["pop_total"] = 500
    b_high = copy.deepcopy(_load_base_bundle())
    b_high["demographic_data"]["pop_total"] = 3000
    assert score(b_high)["demand_score"] > score(b_low)["demand_score"]


def test_monotonicity_pressure_increases_with_competitors():
    b_low = copy.deepcopy(_load_base_bundle())
    b_low["competitor_data"]["summary"]["total_count"] = 2
    b_high = copy.deepcopy(_load_base_bundle())
    b_high["competitor_data"]["summary"]["total_count"] = 35
    assert score(b_high)["competition_pressure_score"] > score(b_low)["competition_pressure_score"]


def test_monotonicity_confidence_drops_with_nulls():
    clean = copy.deepcopy(_load_base_bundle())
    clean["demographic_data"]["college_student_population_pct"] = 0.35
    clean["demographic_data"]["median_household_income"] = 62000
    clean["demographic_data"]["rent_to_income_ratio"] = 0.28
    dirty = copy.deepcopy(_load_base_bundle())
    dirty["demographic_data"]["college_student_population_pct"] = None
    dirty["demographic_data"]["median_household_income"] = None
    dirty["demographic_data"]["rent_to_income_ratio"] = None
    assert score(clean)["confidence_score"] > score(dirty)["confidence_score"]


def test_scenario_high_demand_low_competition():
    bundle = copy.deepcopy(_load_base_bundle())
    bundle["demographic_data"]["pop_total"] = 4000
    bundle["demographic_data"]["age_22_34_count"] = 500
    bundle["competitor_data"]["summary"]["total_count"] = 2
    bundle["competitor_data"]["summary"]["avg_rating"] = 3.5
    bundle["competitor_data"]["summary"]["top_3_review_share_pct"] = 20
    result = score(bundle)
    assert result["demand_score"] > 60
    assert result["competition_pressure_score"] < 40
    assert result["status"] in ["GO", "CAUTION"]


def test_scenario_saturated_market():
    bundle = copy.deepcopy(_load_base_bundle())
    bundle["competitor_data"]["summary"]["total_count"] = 38
    bundle["competitor_data"]["summary"]["avg_rating"] = 4.8
    bundle["competitor_data"]["summary"]["top_3_review_share_pct"] = 65
    bundle["demographic_data"]["pop_total"] = 1542
    bundle["demographic_data"]["age_22_34_count"] = 158
    result = score(bundle)
    assert result["competition_pressure_score"] > 70
    assert "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION" in result["flags"]
    assert result["status"] in ["CAUTION", "DO_NOT_ENTER"]


def test_scenario_data_desert_still_scores():
    bundle = copy.deepcopy(_load_base_bundle())
    bundle["demographic_data"]["college_student_population_pct"] = None
    bundle["demographic_data"]["median_household_income"] = None
    bundle["demographic_data"]["rent_to_income_ratio"] = None
    result = score(bundle)
    assert result is not None
    assert "DATA_DESERT" in result["flags"]
    assert result["confidence_score"] <= 74.0
    assert result["demand_score"] is not None


def test_scenario_goldmine_triggers_go():
    bundle = copy.deepcopy(_load_base_bundle())
    bundle["competitor_data"]["summary"]["total_count"] = 0
    bundle["demographic_data"]["pop_total"] = 3000
    result = score(bundle)
    assert "GOLDMINE_ZERO_COMPETITORS" in result["flags"]
    assert result["opportunity_score"] == 100.0
    assert result["status"] == "GO"
