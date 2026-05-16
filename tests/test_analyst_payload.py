from pathlib import Path

from decision_engine.analyst_payload import build_analyst_payload


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = str(REPO_ROOT / "config" / "decision_logic_rules.json")


def _scores(**kwargs: float) -> dict:
    return {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
        **kwargs,
    }


def test_payload_has_all_keys():
    result = build_analyst_payload(_scores(), [], rules_path=RULES_PATH)
    assert set(result.keys()) == {
        "metadata",
        "executive_decision",
        "trade_offs",
        "risks",
        "levers",
        "what_would_change",
        "scenario_scores",
        "evidence",
    }


def test_metadata_fields():
    result = build_analyst_payload(_scores(), [], business_type="coffee_shop", rules_path=RULES_PATH)
    md = result["metadata"]
    assert md["spec_version"] == "phase3_decision_intelligence_v0.1"
    assert md["phase2_spec_ref"] == "phase2_scoring_spec_v0.1"
    assert md["business_type"] == "coffee_shop"
    assert isinstance(md["business_profile"], dict)
    assert md["business_profile"] != {}


def test_unknown_business_type_returns_empty_profile():
    result = build_analyst_payload(
        _scores(),
        [],
        business_type="unknown_type",
        rules_path=RULES_PATH,
    )
    assert result["metadata"]["business_profile"] == {}


def test_executive_decision_matches_evaluator():
    result = build_analyst_payload(_scores(), ["REJECTED_DESERT"], rules_path=RULES_PATH)
    ed = result["executive_decision"]
    assert ed["final_status"] == "NO-GO"
    assert ed["status_rule_id"] == "STATUS_REJECTED_DESERT"


def test_evidence_preserves_inputs():
    scores = _scores()
    flags = ["DATA_DESERT"]
    result = build_analyst_payload(scores, flags, rules_path=RULES_PATH)
    assert result["evidence"]["scores"] is scores
    assert result["evidence"]["flags"] is flags


def test_scenario_scores_present():
    result = build_analyst_payload(_scores(), [], rules_path=RULES_PATH)
    assert len(result["scenario_scores"]) == 3


def test_bu_golden_snapshot():
    bu_scores = {
        "demand_score": 65.40,
        "competition_pressure_score": 51.08,
        "market_gap_score": 60.46,
        "risk_score": 58.70,
        "opportunity_score": 60.38,
        "confidence_score": 74.0,
    }
    bu_flags = ["DATA_DESERT"]
    result = build_analyst_payload(bu_scores, bu_flags, rules_path=RULES_PATH)
    assert result["executive_decision"]["final_status"] == "CAUTION"
    assert result["executive_decision"]["status_rule_id"] == "STATUS_DATA_DESERT_CAUTION"
    assert len(result["scenario_scores"]) == 3
    assert result["evidence"]["flags"] == ["DATA_DESERT"]
    assert result["metadata"]["business_profile"] != {}
