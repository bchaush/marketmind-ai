from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from decision_engine.rule_evaluator import evaluate

_IMPACT_WEIGHT: Dict[str, int] = {"high": 0, "medium": 1, "low": 2}


def _lever_sort_key(row: Dict[str, Any]) -> Tuple[int, int, str]:
    imp = str(row.get("impact", "medium")).lower()
    iw = _IMPACT_WEIGHT.get(imp, 1)
    return (-int(row["priority"]), iw, str(row["rule_id"]))


def _resolve_rules_path(rules_path: str) -> Path:
    p = Path(rules_path)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parent.parent / p


def get_levers(
    scores: Dict[str, Any],
    flags: List[str],
    rules_path: str = "config/decision_logic_rules.json",
) -> List[Dict[str, Any]]:
    ev = evaluate(scores, flags, rules_path=rules_path)
    triggered = ev.get("triggered_rule_ids") or []
    lever_ids = [rid for rid in triggered if isinstance(rid, str) and rid.startswith("LEVER_")]
    if not lever_ids:
        return []

    path = _resolve_rules_path(rules_path)
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    lever_rules = data.get("lever_rules")
    if not isinstance(lever_rules, list):
        return []

    id_to_rule: Dict[str, Dict[str, Any]] = {}
    for rule in lever_rules:
        if isinstance(rule, dict) and isinstance(rule.get("rule_id"), str):
            id_to_rule[rule["rule_id"]] = rule

    out: List[Dict[str, Any]] = []
    for rid in lever_ids:
        rule = id_to_rule.get(rid)
        if rule is None:
            continue
        tags = rule.get("output_tags")
        if not isinstance(tags, list):
            continue
        raw_impact = rule.get("impact", "medium")
        impact = raw_impact if isinstance(raw_impact, str) and raw_impact else "medium"
        out.append(
            {
                "rule_id": rid,
                "priority": int(rule["priority"]),
                "impact": impact,
                "output_tags": [t for t in tags if isinstance(t, str)],
            }
        )

    out.sort(key=_lever_sort_key)
    return out
