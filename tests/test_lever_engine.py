import json
from pathlib import Path

from decision_engine.lever_engine import _lever_sort_key, get_levers


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = str(REPO_ROOT / "config" / "decision_logic_rules.json")


def _scores(**kwargs: float) -> dict:
    base = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    base.update(kwargs)
    return base


def test_goldmine_fires_first_mover_lever():
    scores = _scores()
    result = get_levers(scores, ["GOLDMINE_ZERO_COMPETITORS"], rules_path=RULES_PATH)
    row = next(r for r in result if r["rule_id"] == "LEVER_FIRST_MOVER")
    assert row["impact"] == "high"


def test_high_competition_fires_niche_lever():
    scores = _scores(demand_score=65.0, competition_pressure_score=75.0)
    result = get_levers(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "LEVER_NICHE_STUDY_CAFE" in rule_ids


def test_high_risk_fires_reduce_footprint():
    scores = _scores(risk_score=75.0)
    result = get_levers(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "LEVER_REDUCE_FOOTPRINT" in rule_ids


def test_no_levers_for_moderate_scores():
    scores = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "risk_score": 55.0,
        "market_gap_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    result = get_levers(scores, [], rules_path=RULES_PATH)
    assert result == []


def test_output_fields_match_config():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    lever_rules = data["lever_rules"]
    target = next(r for r in lever_rules if r.get("rule_id") == "LEVER_REDUCE_FOOTPRINT")
    expected_tags = list(target["output_tags"])
    expected_impact = str(target["impact"])

    scores = _scores(risk_score=75.0)
    result = get_levers(scores, [], rules_path=RULES_PATH)
    row = next(r for r in result if r["rule_id"] == "LEVER_REDUCE_FOOTPRINT")
    assert row["output_tags"] == expected_tags
    assert row["impact"] == expected_impact


def test_high_impact_before_medium_same_priority():
    medium_first = {
        "rule_id": "LEVER_B_MEDIUM",
        "priority": 70,
        "impact": "medium",
        "output_tags": [],
    }
    high_second = {
        "rule_id": "LEVER_A_HIGH",
        "priority": 70,
        "impact": "high",
        "output_tags": [],
    }
    ordered = sorted([medium_first, high_second], key=_lever_sort_key)
    assert ordered[0]["impact"] == "high"
    assert ordered[1]["impact"] == "medium"
