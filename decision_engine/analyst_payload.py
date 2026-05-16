from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from decision_engine.rule_evaluator import evaluate
from decision_engine.tradeoff_engine import get_tradeoffs
from decision_engine.risk_engine import get_risks
from decision_engine.lever_engine import get_levers
from decision_engine.wwc_engine import get_what_would_change
from decision_engine.scenario_engine import get_scenario_scores


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_rules_path(rules_path: str) -> Path:
    p = Path(rules_path)
    if p.is_absolute():
        return p
    return _repo_root() / p


def _load_phase2_spec_ref(rules_path: str) -> str:
    path = _resolve_rules_path(rules_path)
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    ref = data.get("phase2_spec_ref")
    return ref if isinstance(ref, str) and ref else "phase2_scoring_spec_v0.1"


def _load_business_profile(business_type: str) -> Dict[str, Any]:
    path = _repo_root() / "config" / "business_taxonomy.json"
    try:
        with path.open("r", encoding="utf-8") as f:
            tax: Dict[str, Any] = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    bt = tax.get("business_types")
    if not isinstance(bt, dict):
        return {}

    entry = bt.get(business_type)
    if not isinstance(entry, dict):
        return {}

    profile = entry.get("decision_profile")
    if isinstance(profile, dict):
        return dict(profile)
    return {}


def build_analyst_payload(
    scores: Dict[str, Any],
    flags: List[str],
    business_type: str = "coffee_shop",
    rules_path: str = "config/decision_logic_rules.json",
) -> Dict[str, Any]:
    ed = evaluate(scores, flags, rules_path=rules_path)
    trade_offs = get_tradeoffs(scores, flags, rules_path=rules_path)
    risks = get_risks(scores, flags, rules_path=rules_path)
    levers = get_levers(scores, flags, rules_path=rules_path)
    what_would_change = get_what_would_change(scores, flags, rules_path=rules_path)
    scenario_scores = get_scenario_scores(scores, rules_path=rules_path)

    phase2_spec_ref = _load_phase2_spec_ref(rules_path)
    business_profile = _load_business_profile(business_type)

    return {
        "metadata": {
            "spec_version": "phase3_decision_intelligence_v0.1",
            "phase2_spec_ref": phase2_spec_ref,
            "business_type": business_type,
            "business_profile": business_profile,
        },
        "executive_decision": {
            "final_status": ed["final_status"],
            "status_rule_id": ed["status_rule_id"],
            "triggered_rule_ids": list(ed["triggered_rule_ids"]),
            "triggered_tags": list(ed["triggered_tags"]),
        },
        "trade_offs": trade_offs,
        "risks": risks,
        "levers": levers,
        "what_would_change": what_would_change,
        "scenario_scores": scenario_scores,
        "evidence": {
            "scores": scores,
            "flags": flags,
        },
    }
