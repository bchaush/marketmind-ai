import json
from pathlib import Path

from decision_engine.analyst_payload import build_analyst_payload
from scoring_engine.scoring_engine import score


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_phase2_to_phase3_pipeline_bu_mock():
    mock_path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    bundle = json.loads(mock_path.read_text(encoding="utf-8"))

    phase2 = score(bundle)

    score_keys = (
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    )
    scores = {k: phase2[k] for k in score_keys}
    flags = list(phase2["flags"])

    payload = build_analyst_payload(scores, flags)

    assert payload["executive_decision"]["final_status"] == "CAUTION"
    assert payload["executive_decision"]["status_rule_id"] == "STATUS_DATA_DESERT_CAUTION"
    assert len(payload["scenario_scores"]) == 3
    assert payload["evidence"]["scores"] == scores
    assert payload["evidence"]["flags"] == flags
    assert payload["metadata"]["business_type"] == "coffee_shop"
    assert payload["metadata"]["business_profile"] != {}
    assert any(
        "DATA_DESERT" in rid for rid in payload["executive_decision"]["triggered_rule_ids"]
    )
