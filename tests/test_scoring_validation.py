import copy
import json
from pathlib import Path

from scoring_engine.scoring_engine import score


REPO_ROOT = Path(__file__).resolve().parents[1]


def _clean_bundle():
    bundle = json.loads(
        (REPO_ROOT / "mock_data" / "mock_boston_data.json").read_text(encoding="utf-8")
    )
    b = copy.deepcopy(bundle)
    b["demographic_data"]["college_student_population_pct"] = 0.35
    b["demographic_data"]["median_household_income"] = 62000
    b["demographic_data"]["rent_to_income_ratio"] = 0.28
    return b


def test_direction_income_reduces_risk():
    low_income = _clean_bundle()
    low_income["demographic_data"]["median_household_income"] = 30000
    high_income = _clean_bundle()
    high_income["demographic_data"]["median_household_income"] = 120000
    assert score(high_income)["risk_score"] < score(low_income)["risk_score"]


def test_direction_rating_increases_pressure():
    low_rating = _clean_bundle()
    low_rating["competitor_data"]["summary"]["avg_rating"] = 3.2
    high_rating = _clean_bundle()
    high_rating["competitor_data"]["summary"]["avg_rating"] = 4.9
    assert score(high_rating)["competition_pressure_score"] > score(low_rating)["competition_pressure_score"]


def test_direction_rent_increases_risk():
    low_rent = _clean_bundle()
    low_rent["demographic_data"]["rent_to_income_ratio"] = 0.10
    high_rent = _clean_bundle()
    high_rent["demographic_data"]["rent_to_income_ratio"] = 0.50
    assert score(high_rent)["risk_score"] > score(low_rent)["risk_score"]


def test_direction_top3_increases_pressure():
    low_share = _clean_bundle()
    low_share["competitor_data"]["summary"]["top_3_review_share_pct"] = 10
    high_share = _clean_bundle()
    high_share["competitor_data"]["summary"]["top_3_review_share_pct"] = 80
    assert score(high_share)["competition_pressure_score"] > score(low_share)["competition_pressure_score"]


def test_boundary_goldmine_does_not_fire_at_2500():
    bundle = _clean_bundle()
    bundle["demographic_data"]["pop_total"] = 2500
    bundle["competitor_data"]["summary"]["total_count"] = 0
    result = score(bundle)
    assert "GOLDMINE_ZERO_COMPETITORS" not in result["flags"]


def test_boundary_goldmine_fires_at_2501():
    bundle = _clean_bundle()
    bundle["demographic_data"]["pop_total"] = 2501
    bundle["competitor_data"]["summary"]["total_count"] = 0
    result = score(bundle)
    assert "GOLDMINE_ZERO_COMPETITORS" in result["flags"]


def test_boundary_monopoly_does_not_fire_at_60():
    bundle = _clean_bundle()
    bundle["competitor_data"]["summary"]["top_3_review_share_pct"] = 60
    result = score(bundle)
    assert "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION" not in result["flags"]


def test_boundary_monopoly_fires_at_61():
    bundle = _clean_bundle()
    bundle["competitor_data"]["summary"]["top_3_review_share_pct"] = 61
    result = score(bundle)
    assert "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION" in result["flags"]


def test_confidence_cliff_2_nulls_above_74():
    bundle = _clean_bundle()
    bundle["demographic_data"]["college_student_population_pct"] = None
    bundle["demographic_data"]["rent_to_income_ratio"] = None
    result = score(bundle)
    assert result["confidence_score"] > 74.0
    assert "DATA_DESERT" not in result["flags"]


def test_confidence_cliff_3_nulls_capped_at_74():
    bundle = _clean_bundle()
    bundle["demographic_data"]["college_student_population_pct"] = None
    bundle["demographic_data"]["rent_to_income_ratio"] = None
    bundle["demographic_data"]["median_household_income"] = None
    result = score(bundle)
    assert result["confidence_score"] == 74.0
    assert "DATA_DESERT" in result["flags"]


def test_logic_impossible_market_is_not_go():
    bundle = copy.deepcopy(
        json.loads((REPO_ROOT / "mock_data" / "mock_boston_data.json").read_text(encoding="utf-8"))
    )
    bundle["demographic_data"]["pop_total"] = 9000
    bundle["demographic_data"]["age_22_34_count"] = 1200
    bundle["demographic_data"]["college_student_population_pct"] = 0.70
    bundle["demographic_data"]["median_household_income"] = 85000
    bundle["demographic_data"]["rent_to_income_ratio"] = 0.45
    bundle["competitor_data"]["summary"]["total_count"] = 38
    bundle["competitor_data"]["summary"]["avg_rating"] = 4.9
    bundle["competitor_data"]["summary"]["top_3_review_share_pct"] = 72
    bundle["demographic_data"]["geography_level"] = "block_group"
    bundle["demographic_data"]["confidence_score"] = 100
    bundle["demographic_data"]["fallback_used"] = []
    result = score(bundle)
    assert result["status"] != "GO"
    assert result["market_gap_score"] < 80
    assert "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION" in result["flags"]
