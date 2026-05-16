import json
from pathlib import Path

from decision_engine.tradeoff_engine import get_tradeoffs


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


def test_high_demand_high_competition_fires():
    scores = _scores(demand_score=75.0, competition_pressure_score=75.0)
    result = get_tradeoffs(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "TRADEOFF_HIGH_DEMAND_HIGH_COMPETITION" in rule_ids


def test_no_tradeoff_for_moderate_scores():
    scores = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "risk_score": 55.0,
        "market_gap_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    result = get_tradeoffs(scores, [], rules_path=RULES_PATH)
    assert result == []


def test_tradeoffs_sorted_by_priority():
    scores = _scores(
        demand_score=75.0,
        competition_pressure_score=75.0,
        market_gap_score=70.0,
        risk_score=80.0,
        confidence_score=50.0,
    )
    result = get_tradeoffs(scores, [], rules_path=RULES_PATH)
    assert len(result) >= 2
    prios = [r["priority"] for r in result]
    assert prios == sorted(prios, reverse=True)


def test_output_contains_only_tradeoff_rules():
    scores = _scores(
        demand_score=75.0,
        competition_pressure_score=75.0,
        market_gap_score=65.0,
        risk_score=80.0,
        confidence_score=50.0,
    )
    result = get_tradeoffs(scores, [], rules_path=RULES_PATH)
    assert len(result) >= 1
    for row in result:
        assert row["rule_id"].startswith("TRADEOFF_")


def test_output_tags_match_config():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    trade_rules = data["trade_off_rules"]
    target = next(
        r for r in trade_rules if r.get("rule_id") == "TRADEOFF_HIGH_DEMAND_HIGH_COMPETITION"
    )
    expected_tags = list(target["output_tags"])

    scores = _scores(demand_score=75.0, competition_pressure_score=75.0)
    result = get_tradeoffs(scores, [], rules_path=RULES_PATH)
    row = next(r for r in result if r["rule_id"] == "TRADEOFF_HIGH_DEMAND_HIGH_COMPETITION")
    assert row["output_tags"] == expected_tags
