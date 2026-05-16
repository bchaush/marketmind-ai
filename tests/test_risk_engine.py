import json
from pathlib import Path

from decision_engine.risk_engine import get_risks


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


def test_data_desert_flag_fires_risk():
    scores = _scores()
    result = get_risks(scores, ["DATA_DESERT"], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "RISK_DATA_DESERT" in rule_ids


def test_monopoly_flag_fires_risk():
    scores = _scores()
    result = get_risks(
        scores,
        ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"],
        rules_path=RULES_PATH,
    )
    rule_ids = [r["rule_id"] for r in result]
    assert "RISK_MONOPOLY_CONCENTRATION" in rule_ids


def test_high_rent_burden_fires():
    scores = _scores(risk_score=75.0)
    result = get_risks(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "RISK_HIGH_RENT_BURDEN" in rule_ids


def test_low_confidence_fires():
    scores = _scores(confidence_score=45.0)
    result = get_risks(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "RISK_LOW_CONFIDENCE_FLOOR" in rule_ids


def test_output_tags_match_config():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    risk_rules = data["risk_rules"]
    target = next(r for r in risk_rules if r.get("rule_id") == "RISK_HIGH_RENT_BURDEN")
    expected_tags = list(target["output_tags"])

    scores = _scores(risk_score=75.0)
    result = get_risks(scores, [], rules_path=RULES_PATH)
    row = next(r for r in result if r["rule_id"] == "RISK_HIGH_RENT_BURDEN")
    assert row["output_tags"] == expected_tags
