import json
from pathlib import Path

import pytest

from decision_engine.rule_evaluator import evaluate


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = str(REPO_ROOT / "config" / "decision_logic_rules.json")


def _load_rules_raw() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _priority_map(data: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for group in (
        "status_assignment_rules",
        "trade_off_rules",
        "risk_rules",
        "lever_rules",
        "what_would_change_rules",
        "scenario_rules",
    ):
        lst = data.get(group)
        if not isinstance(lst, list):
            continue
        for rule in lst:
            if isinstance(rule, dict) and "rule_id" in rule:
                out[str(rule["rule_id"])] = int(rule["priority"])
    return out


def _base_scores() -> dict:
    return {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }


def test_missing_score_key_raises():
    scores = _base_scores()
    del scores["risk_score"]
    with pytest.raises(ValueError, match="risk_score"):
        evaluate(scores, [], rules_path=RULES_PATH)


def test_none_score_does_not_crash():
    scores = _base_scores()
    scores["risk_score"] = None
    result = evaluate(scores, [], rules_path=RULES_PATH)
    assert isinstance(result, dict)
    assert "final_status" in result
    assert "status_rule_id" in result


def test_rejected_desert_flag_forces_no_go():
    scores = _base_scores()
    result = evaluate(scores, ["REJECTED_DESERT"], rules_path=RULES_PATH)
    assert result["final_status"] == "NO-GO"
    assert result["status_rule_id"] == "STATUS_REJECTED_DESERT"


def test_monopoly_flag_forces_caution():
    scores = _base_scores()
    result = evaluate(
        scores,
        ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"],
        rules_path=RULES_PATH,
    )
    assert result["final_status"] == "CAUTION"
    assert result["status_rule_id"] == "STATUS_MONOPOLY_FORCE_CAUTION"


def test_goldmine_flag_forces_go():
    scores = _base_scores()
    result = evaluate(scores, ["GOLDMINE_ZERO_COMPETITORS"], rules_path=RULES_PATH)
    assert result["final_status"] == "GO"
    assert result["status_rule_id"] == "STATUS_GOLDMINE_GO"


def test_data_desert_flag_forces_caution():
    scores = _base_scores()
    result = evaluate(scores, ["DATA_DESERT"], rules_path=RULES_PATH)
    assert result["final_status"] == "CAUTION"
    assert result["status_rule_id"] == "STATUS_DATA_DESERT_CAUTION"


def test_high_risk_score_forces_no_go():
    scores = _base_scores()
    scores["risk_score"] = 85.0
    result = evaluate(scores, [], rules_path=RULES_PATH)
    assert result["final_status"] == "NO-GO"
    assert result["status_rule_id"] == "STATUS_HIGH_RISK_NO_GO"


def test_strong_go_conditions():
    scores = _base_scores()
    scores["demand_score"] = 80.0
    scores["competition_pressure_score"] = 40.0
    scores["risk_score"] = 35.0
    result = evaluate(scores, [], rules_path=RULES_PATH)
    assert result["final_status"] == "GO"
    assert result["status_rule_id"] == "STATUS_STRONG_GO"


def test_default_caution():
    scores = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    result = evaluate(scores, [], rules_path=RULES_PATH)
    assert result["final_status"] == "CAUTION"
    assert result["status_rule_id"] == "STATUS_DEFAULT_CAUTION"


def test_triggered_rule_ids_sorted_by_priority():
    data = _load_rules_raw()
    pmap = _priority_map(data)
    scores = _base_scores()
    scores["demand_score"] = 65.0
    result = evaluate(scores, ["DATA_DESERT"], rules_path=RULES_PATH)
    ids = result["triggered_rule_ids"]
    assert len(ids) >= 2
    prios = [pmap[i] for i in ids]
    assert prios == sorted(prios, reverse=True)


def test_triggered_tags_no_duplicates():
    scores = _base_scores()
    result = evaluate(
        scores,
        ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"],
        rules_path=RULES_PATH,
    )
    tags = result["triggered_tags"]
    assert len(tags) == len(set(tags))


def test_rejected_desert_beats_goldmine():
    scores = _base_scores()
    result = evaluate(
        scores,
        ["REJECTED_DESERT", "GOLDMINE_ZERO_COMPETITORS"],
        rules_path=RULES_PATH,
    )
    assert result["final_status"] == "NO-GO"
    assert result["status_rule_id"] == "STATUS_REJECTED_DESERT"
