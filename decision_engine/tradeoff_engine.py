from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from decision_engine.rule_evaluator import evaluate


def _resolve_rules_path(rules_path: str) -> Path:
    p = Path(rules_path)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parent.parent / p


def get_tradeoffs(
    scores: Dict[str, Any],
    flags: List[str],
    rules_path: str = "config/decision_logic_rules.json",
) -> List[Dict[str, Any]]:
    ev = evaluate(scores, flags, rules_path=rules_path)
    triggered = ev.get("triggered_rule_ids") or []
    tradeoff_ids = [rid for rid in triggered if isinstance(rid, str) and rid.startswith("TRADEOFF_")]
    if not tradeoff_ids:
        return []

    path = _resolve_rules_path(rules_path)
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    trade_rules = data.get("trade_off_rules")
    if not isinstance(trade_rules, list):
        return []

    id_to_rule: Dict[str, Dict[str, Any]] = {}
    for rule in trade_rules:
        if isinstance(rule, dict) and isinstance(rule.get("rule_id"), str):
            id_to_rule[rule["rule_id"]] = rule

    out: List[Dict[str, Any]] = []
    for rid in tradeoff_ids:
        rule = id_to_rule.get(rid)
        if rule is None:
            continue
        tags = rule.get("output_tags")
        if not isinstance(tags, list):
            continue
        out.append(
            {
                "rule_id": rid,
                "priority": int(rule["priority"]),
                "output_tags": [t for t in tags if isinstance(t, str)],
            }
        )

    out.sort(key=lambda x: (-x["priority"], x["rule_id"]))
    return out
