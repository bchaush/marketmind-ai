from __future__ import annotations

from typing import Any

_FLAG_LABELS: dict[str, str] = {
    "DATA_DESERT": "Incomplete local data coverage",
    "STATUS_DATA_DESERT_CAUTION": "Caution: limited data confidence in this area",
    "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION": "High market consolidation risk",
    "STATUS_MONOPOLY_FORCE_CAUTION": "Caution: dominant incumbents detected",
    "GOLDMINE_ZERO_COMPETITORS": "Untapped market opportunity detected",
    "STATUS_GOLDMINE_GO": "Strong market opportunity confirmed",
    "STATUS_HIGH_RISK_NO_GO": "High risk — market entry not recommended",
    "STATUS_DEFAULT_CAUTION": "Proceed with caution — mixed market signals",
    "STATUS_REJECTED_DESERT": "No-Go: insufficient demographic data at this location",
    "REJECTED_DESERT": "Insufficient demographic data at this location",
    "TO_GO_BLOCK_GROUP_DATA": "Analysis would upgrade to GO if block-group level data becomes available",
    "TO_NO_GO_PLACEHOLDER_GEOGRAPHY": "Analysis would downgrade to NO-GO if only placeholder geography is available",
}


def _translate_flags(flags: list[str]) -> list[str]:
    return [_FLAG_LABELS.get(f, f) for f in flags]

SYSTEM_PROMPT = """You are a senior market analyst writing a structured investment briefing.
Follow these rules without exception:

DATA RULES:
- Every numeric claim must cite the exact value from the market data.
  Do not round, adjust, or invent numbers.
- Every risk, lever, scenario you reference must appear in the market
  data context. Do not introduce concepts not in the data.
- Every factual claim must be traceable to the payload. Numeric claims
  must use exact provided values. Not every sentence needs a number,
  but no number may be invented.
- what_would_change must only contain items that appear explicitly in
  the <what_would_change> section of <market_context>. If that XML section
  is empty or contains only a comment, what_would_change must be an empty
  list []. Never invent threshold conditions, competitor counts, score
  targets, or flip scenarios. The same rule applies to hidden_risks and
  strategic_levers — only reference items explicitly present in the
  <risks> and <levers> XML sections respectively.

WRITING RULES:
- Write in confident, professional, third-person analyst prose.
- No bullet points in executive_summary or pillar_analysis.
- Do not use "I don't know" or "as an AI".
- Do not add caveats about training data or knowledge cutoff.
- Your recommendation field must match final_status exactly.
  If final_status is CAUTION, recommendation must be "CAUTION".

OUTPUT FORMAT RULES:
- Return valid JSON only.
- Your response must begin with the { character and end with the }
  character. No exceptions.
- Do not include markdown code fences, backticks, preamble,
  commentary, or any text outside the JSON object.
- If you include anything before { or after } the output fails validation.

LENGTH CONSTRAINTS (enforced by validator — stay within these):
- executive_summary: minimum 50 characters, maximum 350 characters.
  Stay well under this limit. Aim for 2 tight sentences, not 3.
- pillar_analysis: minimum 100 characters, maximum 1000 characters.
- strategic_levers: must contain at least 1 string item.

REQUIRED JSON KEYS — include all of these, no extras:
executive_summary, recommendation, pillar_analysis, scenario_analysis,
strategic_levers, hidden_risks, what_would_change, confidence_note.
strategic_levers, hidden_risks, what_would_change are lists of strings.
All other fields are strings."""

_SCORE_TAGS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
)


def _score_xml_value(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _comma_join(items: Any) -> str:
    if not items:
        return "none"
    if not isinstance(items, list):
        return "none"
    parts = [str(item) for item in items if item is not None]
    return ", ".join(parts) if parts else "none"


def _build_scenarios_xml(scenarios: Any) -> str:
    if not scenarios or not isinstance(scenarios, list):
        return "  <scenarios>\n    <!-- empty -->\n  </scenarios>"
    blocks: list[str] = ["  <scenarios>"]
    for item in scenarios:
        if not isinstance(item, dict):
            continue
        scenario_id = str(item.get("scenario_id") or "")
        label = str(item.get("label") or "")
        score = item.get("opportunity_score")
        score_text = "N/A" if score is None else str(score)
        blocks.extend(
            [
                "    <scenario>",
                f"      <id>{scenario_id}</id>",
                f"      <label>{label}</label>",
                f"      <score>{score_text}</score>",
                "    </scenario>",
            ]
        )
    if len(blocks) == 1:
        blocks.append("    <!-- empty -->")
    blocks.append("  </scenarios>")
    return "\n".join(blocks)


def _build_risks_xml(risks: Any) -> str:
    if not risks or not isinstance(risks, list):
        return "  <risks>\n    <!-- empty -->\n  </risks>"
    blocks: list[str] = ["  <risks>"]
    for item in risks:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        severity = str(item.get("severity") or "")
        blocks.extend(
            [
                "    <risk>",
                f"      <label>{label}</label>",
                f"      <severity>{severity}</severity>",
            ]
        )
        flags_raw = item.get("flags")
        if isinstance(flags_raw, list) and flags_raw:
            flag_strs = [str(x) for x in flags_raw if x is not None]
            flags_text = ", ".join(_translate_flags(flag_strs))
            blocks.append(f"      <flags>{flags_text}</flags>")
        blocks.append("    </risk>")
    if len(blocks) == 1:
        blocks.append("    <!-- empty -->")
    blocks.append("  </risks>")
    return "\n".join(blocks)


def _build_levers_xml(levers: Any) -> str:
    if not levers or not isinstance(levers, list):
        return "  <levers>\n    <!-- empty -->\n  </levers>"
    blocks: list[str] = ["  <levers>"]
    for item in levers:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        action = str(item.get("action") or "")
        blocks.extend(
            [
                "    <lever>",
                f"      <label>{label}</label>",
                f"      <action>{action}</action>",
                "    </lever>",
            ]
        )
    if len(blocks) == 1:
        blocks.append("    <!-- empty -->")
    blocks.append("  </levers>")
    return "\n".join(blocks)


def _build_wwc_xml(wwc: Any) -> str:
    if not wwc or not isinstance(wwc, list):
        return "  <what_would_change>\n    <!-- empty -->\n  </what_would_change>"
    blocks: list[str] = ["  <what_would_change>"]
    for item in wwc:
        if not isinstance(item, dict):
            continue
        condition = str(item.get("condition") or "")
        impact = str(item.get("impact") or "")
        blocks.extend(
            [
                "    <condition>",
                f"      <description>{condition}</description>",
                f"      <impact>{impact}</impact>",
                "    </condition>",
            ]
        )
    if len(blocks) == 1:
        blocks.append("    <!-- empty -->")
    blocks.append("  </what_would_change>")
    return "\n".join(blocks)


def _build_hidden_risks_xml(hidden_risks: Any) -> str:
    """Translate flag-like strings if ui_payload carries a hidden_risks list."""
    if not hidden_risks or not isinstance(hidden_risks, list):
        return ""
    flag_strs = [str(x) for x in hidden_risks if x is not None]
    if not flag_strs:
        return ""
    text = ", ".join(_translate_flags(flag_strs))
    return f"  <hidden_risks>{text}</hidden_risks>"


def _build_user_message(ui_payload: dict) -> str:
    status = ui_payload.get("status") or {}
    if not isinstance(status, dict):
        status = {}

    scores = ui_payload.get("scores") or {}
    if not isinstance(scores, dict):
        scores = {}

    final_status = str(status.get("final_status") or "")
    status_rule_id = str(status.get("status_rule_id") or "")
    status_rule_display = _FLAG_LABELS.get(status_rule_id, status_rule_id)

    score_lines = []
    for tag in _SCORE_TAGS:
        score_lines.append(f"    <{tag}>{_score_xml_value(scores.get(tag))}</{tag}>")
    scores_xml = "\n".join(score_lines)

    raw_flags = ui_payload.get("flags")
    flags_list: list[str] = []
    if isinstance(raw_flags, list):
        flags_list = [str(f) for f in raw_flags if f is not None]
    flags_text = _comma_join(_translate_flags(flags_list))

    null_adj_text = _comma_join(ui_payload.get("null_adjustments"))

    context_parts = [
        "<market_context>",
        "  <status>",
        f"    <final_status>{final_status}</final_status>",
        f"    <status_rule_id>{status_rule_display}</status_rule_id>",
        "  </status>",
        "  <scores>",
        scores_xml,
        "  </scores>",
        f"  <flags>{flags_text}</flags>",
        _build_scenarios_xml(ui_payload.get("scenarios")),
        _build_risks_xml(ui_payload.get("risks")),
    ]
    hr_xml = _build_hidden_risks_xml(ui_payload.get("hidden_risks"))
    if hr_xml:
        context_parts.append(hr_xml)
    context_parts.extend(
        [
            _build_levers_xml(ui_payload.get("levers")),
            _build_wwc_xml(ui_payload.get("what_would_change")),
            f"  <null_adjustments>{null_adj_text}</null_adjustments>",
            "</market_context>",
            "",
            "Using only the data in <market_context>, write the analyst report JSON.",
            "Begin your response with { and end with }. No other text.",
        ]
    )

    return "\n".join(context_parts)


def build_prompt(ui_payload: dict) -> dict[str, str]:
    return {
        "system_prompt": SYSTEM_PROMPT,
        "user_message": _build_user_message(ui_payload),
    }


def preview_prompt(ui_payload: dict) -> None:
    prompt = build_prompt(ui_payload)
    print("=== SYSTEM PROMPT ===")
    print(prompt["system_prompt"])
    print()
    print("=== USER MESSAGE ===")
    print(prompt["user_message"])
