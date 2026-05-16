from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _resolve_rules_path(rules_path: str) -> Path:
    p = Path(rules_path)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parent.parent / p


def get_scenario_scores(
    scores: Dict[str, Any],
    rules_path: str = "config/decision_logic_rules.json",
) -> List[Dict[str, Any]]:
    path = _resolve_rules_path(rules_path)
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    rules = data.get("scenario_rules")
    if not isinstance(rules, list):
        return []

    out: List[Dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rid = rule.get("rule_id")
        scenario = rule.get("scenario")
        weights = rule.get("weights")
        if not isinstance(rid, str) or not isinstance(scenario, str) or not isinstance(weights, dict):
            continue

        weights_applied: Dict[str, float] = {}
        total = 0.0
        any_contrib = False

        for metric, weight in weights.items():
            if not isinstance(metric, str):
                continue
            raw_val = scores.get(metric)
            if raw_val is None:
                continue
            try:
                w = float(weight)
                v = float(raw_val)
            except (TypeError, ValueError):
                continue
            total += v * w
            weights_applied[metric] = w
            any_contrib = True

        if not any_contrib:
            scenario_score = 0.0
            weights_applied = {}
        else:
            scenario_score = max(0.0, min(100.0, total))

        scenario_score = round(float(scenario_score), 2)

        out.append(
            {
                "rule_id": rid,
                "scenario": scenario,
                "scenario_score": scenario_score,
                "weights_applied": dict(weights_applied),
            }
        )

    out.sort(key=lambda x: (-float(x["scenario_score"]), str(x["rule_id"])))
    return out
