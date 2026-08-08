"""Presentation-layer wording for aggregate-risk rules (no trigger/tag contract changes)."""

from __future__ import annotations

import json
from pathlib import Path

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from decision_engine.risk_engine import get_risks
from decision_engine.lever_engine import get_levers
from decision_engine.wwc_engine import get_what_would_change
from report_engine.prompt_builder import SYSTEM_PROMPT, build_prompt
from ui.payload_adapter import adapt


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = REPO_ROOT / "config" / "decision_logic_rules.json"


def _scores(**kwargs: float) -> dict:
    base = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 75.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    base.update(kwargs)
    return base


def test_legacy_output_tags_unchanged_in_config_and_engines() -> None:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    risk = next(r for r in data["risk_rules"] if r["rule_id"] == "RISK_HIGH_RENT_BURDEN")
    lever = next(r for r in data["lever_rules"] if r["rule_id"] == "LEVER_REDUCE_FOOTPRINT")
    wwc = next(r for r in data["what_would_change_rules"] if r["rule_id"] == "WWC_RENT_RELIEF")

    assert risk["output_tags"] == ["HIGH_RENT_BURDEN", "CUSTOMER_FINANCIAL_FRAGILITY"]
    assert lever["output_tags"] == ["REDUCE_FIXED_COSTS", "SMALL_FOOTPRINT_RECOMMENDED"]
    assert wwc["output_tags"] == ["TO_GO_RENT_BELOW_MARKET", "TO_NO_GO_RENT_INCREASE"]

    scores = _scores()
    risk_row = next(
        r for r in get_risks(scores, [], rules_path=str(RULES_PATH))
        if r["rule_id"] == "RISK_HIGH_RENT_BURDEN"
    )
    lever_row = next(
        r for r in get_levers(scores, [], rules_path=str(RULES_PATH))
        if r["rule_id"] == "LEVER_REDUCE_FOOTPRINT"
    )
    wwc_row = next(
        r for r in get_what_would_change(scores, [], rules_path=str(RULES_PATH))
        if r["rule_id"] == "WWC_RENT_RELIEF"
    )
    assert risk_row["output_tags"] == ["HIGH_RENT_BURDEN", "CUSTOMER_FINANCIAL_FRAGILITY"]
    assert lever_row["output_tags"] == ["REDUCE_FIXED_COSTS", "SMALL_FOOTPRINT_RECOMMENDED"]
    assert wwc_row["to_go_tags"] == ["TO_GO_RENT_BELOW_MARKET"]
    assert wwc_row["to_no_go_tags"] == ["TO_NO_GO_RENT_INCREASE"]


def test_aggregate_risk_rules_present_without_rent_specific_ui_claims() -> None:
    raw = build_analyst_payload(_scores(), [])
    ui = adapt(validate_analyst_payload(raw))

    risk = next(r for r in ui["risks"] if r["rule_id"] == "RISK_HIGH_RENT_BURDEN")
    assert risk["label"] == "Elevated Aggregate Risk Signal"
    assert "rent" not in risk["label"].lower()
    assert "fragility" not in risk["severity"].lower()
    assert "aggregate" in risk["severity"].lower()

    lever = next(r for r in ui["levers"] if r["rule_id"] == "LEVER_REDUCE_FOOTPRINT")
    assert lever["label"] == "Fixed-Cost Reduction Hypothesis"
    assert "recommended" not in lever["action"].lower()
    assert "hypothesis" in lever["action"].lower() or "evaluating" in lever["action"].lower()

    assert ui["what_would_change"]
    wwc_blob = " ".join(
        f"{w.get('condition', '')} {w.get('impact', '')}" for w in ui["what_would_change"]
    ).lower()
    assert "hypothetical" in wwc_blob
    assert "below market" not in wwc_blob
    assert "rent increase" not in wwc_blob


def test_prompt_guardrail_rejects_rent_inference_from_aggregate_risk() -> None:
    assert "aggregate risk_score" in SYSTEM_PROMPT
    assert "high rent burden" in SYSTEM_PROMPT.lower()
    assert "validated footprint" in SYSTEM_PROMPT.lower()


def test_prompt_xml_uses_sanitized_aggregate_risk_presentation() -> None:
    """AI context receives adapted prose, not raw legacy tag literals."""
    raw = build_analyst_payload(_scores(), [])
    ui = adapt(validate_analyst_payload(raw))
    prompt = build_prompt(ui)
    user = prompt["user_message"]
    assert "Elevated Aggregate Risk Signal" in user
    assert "High Rent Burden" not in user
    assert "Customer Financial Fragility" not in user
    assert "Small Footprint Recommended" not in user
    assert "HIGH_RENT_BURDEN" not in user
    assert "CUSTOMER_FINANCIAL_FRAGILITY" not in user
    assert "SMALL_FOOTPRINT_RECOMMENDED" not in user
    assert "TO_GO_RENT_BELOW_MARKET" not in user
