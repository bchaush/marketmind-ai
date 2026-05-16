from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from decision_engine.rule_evaluator import evaluate


def _resolve_rules_path(rules_path: str) -> Path:
    p = Path(rules_path)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parent.parent / p


def _split_wwc_tags(tags: List[str]) -> Tuple[List[str], List[str]]:
    to_go: List[str] = []
    to_no_go: List[str] = []
    for t in tags:
        if not isinstance(t, str):
            continue
        if t.startswith("TO_NO_GO_"):
            to_no_go.append(t)
        elif t.startswith("TO_GO_"):
            to_go.append(t)
    return to_go, to_no_go


def get_what_would_change(
    scores: Dict[str, Any],
    flags: List[str],
    rules_path: str = "config/decision_logic_rules.json",
) -> List[Dict[str, Any]]:
    ev = evaluate(scores, flags, rules_path=rules_path)
    triggered = ev.get("triggered_rule_ids") or []
    wwc_ids = [rid for rid in triggered if isinstance(rid, str) and rid.startswith("WWC_")]
    if not wwc_ids:
        return []

    path = _resolve_rules_path(rules_path)
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    wwc_rules = data.get("what_would_change_rules")
    if not isinstance(wwc_rules, list):
        return []

    id_to_rule: Dict[str, Dict[str, Any]] = {}
    for rule in wwc_rules:
        if isinstance(rule, dict) and isinstance(rule.get("rule_id"), str):
            id_to_rule[rule["rule_id"]] = rule

    out: List[Dict[str, Any]] = []
    for rid in wwc_ids:
        rule = id_to_rule.get(rid)
        if rule is None:
            continue
        tags = rule.get("output_tags")
        if not isinstance(tags, list):
            continue
        str_tags = [t for t in tags if isinstance(t, str)]
        to_go, to_no_go = _split_wwc_tags(str_tags)
        out.append(
            {
                "rule_id": rid,
                "priority": int(rule["priority"]),
                "to_go_tags": to_go,
                "to_no_go_tags": to_no_go,
            }
        )

    out.sort(key=lambda x: (-int(x["priority"]), str(x["rule_id"])))
    return out
