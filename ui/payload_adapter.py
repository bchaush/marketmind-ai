from __future__ import annotations

from typing import Any

from decision_engine.payload_schema import AnalystPayload

_STATUS_COLORS = {
    "GO": "green",
    "CAUTION": "orange",
    "NO-GO": "red",
}

_SCORE_KEYS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
)

_RULE_PREFIXES = (
    "TRADEOFF_",
    "RISK_",
    "LEVER_",
    "WWC_",
    "SCENARIO_",
    "STATUS_",
)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _humanize_token(token: str) -> str:
    if not token:
        return ""
    return token.replace("_", " ").strip().title()


def _humanize_rule_id(rule_id: str) -> str:
    if not rule_id:
        return ""
    text = str(rule_id)
    for prefix in _RULE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return _humanize_token(text)


def _tags_text(tags: Any) -> str:
    items = _as_str_list(tags)
    if not items:
        return ""
    return "; ".join(_humanize_token(tag) for tag in items)


def _get_evidence_field(payload: AnalystPayload, field: str) -> Any:
    evidence = getattr(payload, "evidence", None)
    if evidence is None:
        return None
    value = getattr(evidence, field, None)
    if value is not None:
        return value
    dump = evidence.model_dump() if hasattr(evidence, "model_dump") else {}
    if isinstance(dump, dict):
        return dump.get(field)
    return None


def _get_business_profile(payload: AnalystPayload) -> dict[str, Any]:
    metadata = getattr(payload, "metadata", None)
    if metadata is None:
        return {}
    profile = getattr(metadata, "business_profile", None)
    if isinstance(profile, dict):
        return dict(profile)
    return {}


def adapt(payload: AnalystPayload) -> dict:
    executive = getattr(payload, "executive_decision", None)
    final_status = getattr(executive, "final_status", None) if executive else None
    status_rule_id = getattr(executive, "status_rule_id", None) if executive else None

    raw_scores = _get_evidence_field(payload, "scores")
    if not isinstance(raw_scores, dict):
        raw_scores = {}

    scores = {key: _optional_float(raw_scores.get(key)) for key in _SCORE_KEYS}

    tradeoffs_out: list[dict[str, str]] = []
    for item in getattr(payload, "trade_offs", None) or []:
        if item is None:
            continue
        if isinstance(item, dict):
            rule_id = str(item.get("rule_id", "") or "")
            tags = item.get("output_tags")
        else:
            rule_id = str(getattr(item, "rule_id", "") or "")
            tags = getattr(item, "output_tags", None)
        tradeoffs_out.append(
            {
                "rule_id": rule_id,
                "label": _humanize_rule_id(rule_id),
                "description": _tags_text(tags),
            }
        )

    risks_out: list[dict[str, str]] = []
    for item in getattr(payload, "risks", None) or []:
        if item is None:
            continue
        rule_id = str(getattr(item, "rule_id", "") or "")
        tags = getattr(item, "output_tags", None)
        tag_list = _as_str_list(tags)
        risks_out.append(
            {
                "rule_id": rule_id,
                "label": _humanize_rule_id(rule_id),
                "severity": _humanize_token(tag_list[0]) if tag_list else "",
            }
        )

    levers_out: list[dict[str, str]] = []
    for item in getattr(payload, "levers", None) or []:
        if item is None:
            continue
        rule_id = str(getattr(item, "rule_id", "") or "")
        levers_out.append(
            {
                "rule_id": rule_id,
                "label": _humanize_rule_id(rule_id),
                "action": _tags_text(getattr(item, "output_tags", None)),
            }
        )

    wwc_out: list[dict[str, str]] = []
    for item in getattr(payload, "what_would_change", None) or []:
        if item is None:
            continue
        rule_id = str(getattr(item, "rule_id", "") or "")
        to_go = _as_str_list(getattr(item, "to_go_tags", None))
        to_no_go = _as_str_list(getattr(item, "to_no_go_tags", None))
        condition_parts: list[str] = []
        if to_go:
            condition_parts.append(f"To GO: {_tags_text(to_go)}")
        if to_no_go:
            condition_parts.append(f"To NO-GO: {_tags_text(to_no_go)}")
        impact_parts: list[str] = []
        if to_go:
            impact_parts.append(_tags_text(to_go))
        if to_no_go:
            impact_parts.append(_tags_text(to_no_go))
        wwc_out.append(
            {
                "rule_id": rule_id,
                "condition": " | ".join(condition_parts),
                "impact": " | ".join(impact_parts),
            }
        )

    scenarios_out: list[dict[str, Any]] = []
    for item in getattr(payload, "scenario_scores", None) or []:
        if item is None:
            continue
        rule_id = str(getattr(item, "rule_id", "") or "")
        scenario = str(getattr(item, "scenario", "") or "")
        scenario_id = scenario or rule_id
        scenarios_out.append(
            {
                "scenario_id": scenario_id,
                "label": _humanize_token(scenario) if scenario else _humanize_rule_id(rule_id),
                "opportunity_score": float(getattr(item, "scenario_score", 0.0) or 0.0),
            }
        )

    status_key = str(final_status) if final_status is not None else ""
    color = _STATUS_COLORS.get(status_key, "")

    return {
        "status": {
            "final_status": status_key,
            "status_rule_id": str(status_rule_id) if status_rule_id is not None else "",
            "color": color,
        },
        "scores": scores,
        "flags": _as_str_list(_get_evidence_field(payload, "flags")),
        "null_adjustments": _as_str_list(_get_evidence_field(payload, "null_adjustments")),
        "tradeoffs": tradeoffs_out,
        "risks": risks_out,
        "levers": levers_out,
        "what_would_change": wwc_out,
        "scenarios": scenarios_out,
        "business_profile": _get_business_profile(payload),
    }
