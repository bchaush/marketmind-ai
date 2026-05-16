import json
from pathlib import Path

from decision_engine.wwc_engine import get_what_would_change


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


def test_high_competition_fires_wwc():
    scores = _scores(competition_pressure_score=70.0)
    result = get_what_would_change(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "WWC_COMPETITOR_EXIT" in rule_ids


def test_high_risk_fires_wwc():
    scores = _scores(risk_score=75.0)
    result = get_what_would_change(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "WWC_RENT_RELIEF" in rule_ids


def test_low_confidence_fires_wwc():
    scores = _scores(confidence_score=45.0)
    result = get_what_would_change(scores, [], rules_path=RULES_PATH)
    rule_ids = [r["rule_id"] for r in result]
    assert "WWC_DATA_CONFIDENCE" in rule_ids


def test_no_wwc_for_moderate_scores():
    scores = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "risk_score": 55.0,
        "market_gap_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    result = get_what_would_change(scores, [], rules_path=RULES_PATH)
    assert result == []


def test_tags_split_correctly():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    wwc_rules = data["what_would_change_rules"]
    target = next(r for r in wwc_rules if r.get("rule_id") == "WWC_COMPETITOR_EXIT")
    expected_all = [t for t in target["output_tags"] if isinstance(t, str)]

    scores = _scores(competition_pressure_score=70.0)
    result = get_what_would_change(scores, [], rules_path=RULES_PATH)
    row = next(r for r in result if r["rule_id"] == "WWC_COMPETITOR_EXIT")

    for t in row["to_go_tags"]:
        assert t.startswith("TO_GO_")
    for t in row["to_no_go_tags"]:
        assert t.startswith("TO_NO_GO_")
    for t in row["to_go_tags"]:
        assert not t.startswith("TO_NO_GO_")

    combined = row["to_go_tags"] + row["to_no_go_tags"]
    assert sorted(combined) == sorted(expected_all)
