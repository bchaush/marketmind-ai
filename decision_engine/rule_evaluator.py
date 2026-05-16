from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, MutableMapping, Optional, Tuple, TypedDict

_OPERATORS: Dict[str, Callable[[float, float], bool]] = {
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
}

_RULES_CACHE: Optional[Dict[str, Any]] = None
_CACHED_RULES_PATH: Optional[str] = None

_REQUIRED_SCORE_KEYS: frozenset[str] = frozenset(
    {
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    }
)

_RULE_GROUPS_VALIDATE: Tuple[str, ...] = (
    "status_assignment_rules",
    "trade_off_rules",
    "risk_rules",
    "lever_rules",
    "what_would_change_rules",
    "scenario_rules",
)

_RULE_GROUPS_EVALUATE: Tuple[str, ...] = (
    "status_assignment_rules",
    "trade_off_rules",
    "risk_rules",
    "lever_rules",
    "what_would_change_rules",
)


class EvaluateResult(TypedDict):
    final_status: str
    status_rule_id: str
    triggered_rule_ids: List[str]
    triggered_tags: List[str]


def _resolve_rules_path(rules_path: str) -> Path:
    p = Path(rules_path)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parent.parent / p


def _load_rules(rules_path: str = "config/decision_logic_rules.json") -> Dict[str, Any]:
    global _RULES_CACHE, _CACHED_RULES_PATH
    resolved = str(_resolve_rules_path(rules_path).resolve())
    if _RULES_CACHE is not None and _CACHED_RULES_PATH == resolved:
        return _RULES_CACHE

    path = Path(resolved)
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    _RULES_CACHE = data
    _CACHED_RULES_PATH = resolved
    return _RULES_CACHE


def _validate_config_rules(data: Dict[str, Any]) -> None:
    for group in _RULE_GROUPS_VALIDATE:
        rules = data.get(group)
        if rules is None:
            continue
        if not isinstance(rules, list):
            raise ValueError("Group {!r} must be a list".format(group))
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ValueError("Rule at index {} in {!r} must be an object".format(idx, group))
            rid = rule.get("rule_id")
            if rid is None or rid == "":
                raise ValueError("Missing rule_id in group {!r} at index {}".format(group, idx))
            if "priority" not in rule:
                raise ValueError(str(rid))
            if group == "scenario_rules":
                if "scenario" not in rule or "weights" not in rule:
                    raise ValueError(str(rid))
            else:
                if "output_tags" not in rule:
                    raise ValueError(str(rid))
                if not isinstance(rule["output_tags"], list):
                    raise ValueError(str(rid))


def _validate_scores(scores: MutableMapping[str, Any]) -> None:
    missing = sorted(_REQUIRED_SCORE_KEYS - set(scores.keys()))
    if missing:
        raise ValueError(
            "scores dict missing required keys: {}".format(", ".join(missing))
        )


def _condition_dict_satisfied(cond: Dict[str, Any], scores: Dict[str, Any]) -> bool:
    evaluated_any = False
    for metric, ops in cond.items():
        raw_val = scores.get(metric)
        if raw_val is None:
            continue
        evaluated_any = True
        if not isinstance(ops, dict):
            raise ValueError(
                "Invalid condition for metric {!r}: expected object".format(metric)
            )
        try:
            val = float(raw_val)
        except (TypeError, ValueError) as e:
            raise ValueError(
                "Non-numeric score for metric {!r}: {!r}".format(metric, raw_val)
            ) from e

        for op_name, threshold in ops.items():
            if op_name not in _OPERATORS:
                raise ValueError("Unknown operator {!r} for metric {!r}".format(op_name, metric))
            try:
                thr = float(threshold)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    "Non-numeric threshold for {!r}.{}: {!r}".format(metric, op_name, threshold)
                ) from e
            if not _OPERATORS[op_name](val, thr):
                return False

    return evaluated_any


def _rule_fires(rule: Dict[str, Any], scores: Dict[str, Any], flags: List[str]) -> bool:
    has_flag = "flag" in rule
    has_condition = "condition" in rule

    if not has_flag and not has_condition:
        return False

    flag_ok = False
    if has_flag:
        f = rule.get("flag")
        if isinstance(f, str) and f in flags:
            flag_ok = True

    cond_ok = False
    if has_condition:
        cond = rule["condition"]
        if cond == "default":
            cond_ok = True
        elif isinstance(cond, dict):
            cond_ok = _condition_dict_satisfied(cond, scores)

    if has_flag and has_condition:
        return flag_ok or cond_ok
    if has_flag:
        return flag_ok
    return cond_ok


def _collect_fired_for_group(
    data: Dict[str, Any],
    group: str,
    scores: Dict[str, Any],
    flags: List[str],
) -> List[Dict[str, Any]]:
    rules = data.get(group)
    if not isinstance(rules, list):
        return []
    out: List[Dict[str, Any]] = []
    for rule in rules:
        if isinstance(rule, dict) and _rule_fires(rule, scores, flags):
            out.append(rule)
    return out


def evaluate(
    scores: Dict[str, Any],
    flags: List[str],
    rules_path: str = "config/decision_logic_rules.json",
) -> EvaluateResult:
    _validate_scores(scores)

    data = _load_rules(rules_path)
    _validate_config_rules(data)

    fired: List[Dict[str, Any]] = []
    for group in _RULE_GROUPS_EVALUATE:
        fired.extend(_collect_fired_for_group(data, group, scores, flags))

    fired_sorted = sorted(
        fired,
        key=lambda r: (-int(r["priority"]), str(r.get("rule_id", ""))),
    )

    triggered_rule_ids: List[str] = [str(r["rule_id"]) for r in fired_sorted]

    seen_tags: set[str] = set()
    triggered_tags: List[str] = []
    for rule in fired_sorted:
        tags = rule.get("output_tags")
        if not isinstance(tags, list):
            continue
        for t in tags:
            if not isinstance(t, str):
                continue
            if t not in seen_tags:
                seen_tags.add(t)
                triggered_tags.append(t)

    status_rules = data.get("status_assignment_rules")
    if not isinstance(status_rules, list):
        raise ValueError("status_assignment_rules missing or not a list")

    status_fired = _collect_fired_for_group(
        data, "status_assignment_rules", scores, flags
    )
    status_sorted = sorted(
        status_fired,
        key=lambda r: (-int(r["priority"]), str(r.get("rule_id", ""))),
    )

    if not status_sorted:
        defaults = [
            r
            for r in status_rules
            if isinstance(r, dict) and r.get("condition") == "default"
        ]
        if not defaults:
            raise ValueError("No default status_assignment rule found")
        status_pick = max(
            defaults,
            key=lambda r: (-int(r["priority"]), str(r.get("rule_id", ""))),
        )
    else:
        status_pick = status_sorted[0]

    final_st = status_pick.get("status")
    if not isinstance(final_st, str) or final_st == "":
        raise ValueError(
            "status_assignment rule {!r} missing valid status".format(status_pick.get("rule_id"))
        )

    return {
        "final_status": final_st,
        "status_rule_id": str(status_pick["rule_id"]),
        "triggered_rule_ids": triggered_rule_ids,
        "triggered_tags": triggered_tags,
    }
