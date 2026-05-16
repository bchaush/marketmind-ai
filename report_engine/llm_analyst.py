from __future__ import annotations

import json
import logging
import sys
from typing import Any

import anthropic

from config.secrets import anthropic_api_key
from report_engine.prompt_builder import _FLAG_LABELS, build_prompt
from report_engine.report_schema import AnalystReport, validate_report

logger = logging.getLogger(__name__)


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=anthropic_api_key(), timeout=25.0)


_MODEL = "claude-sonnet-4-5-20250929"
_MAX_TOKENS = 1500
_TEMPERATURE = 0.2


class LLMQuotaExceededError(Exception):
    """Raised when the Anthropic API returns 429."""

    pass


def _fmt_score_val(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _confidence_band_note(confidence_score: Any) -> str:
    if confidence_score is None:
        return "Confidence data unavailable."
    try:
        c = float(confidence_score)
    except (TypeError, ValueError):
        return "Confidence data unavailable."
    if c >= 75:
        return "High confidence — suitable for investment screening"
    if c >= 45:
        return "Moderate confidence — directional insight, verify before committing"
    return "Low confidence — suitable for initial screening only, not investment decisions"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _pillar_analysis_from_scores(scores: dict[str, Any]) -> str:
    specs = (
        ("Demand", "demand_score"),
        ("Competition pressure", "competition_pressure_score"),
        ("Market gap", "market_gap_score"),
        ("Risk", "risk_score"),
        ("Opportunity", "opportunity_score"),
    )
    lines: list[str] = []
    for title, key in specs:
        v = _fmt_score_val(scores.get(key))
        if v is not None:
            lines.append(f"{title}: {v}/100.")
    if not lines:
        base = (
            "Insufficient data to complete pillar analysis. "
            "Macro pillar scores were unavailable for one or more inputs; "
            "refer to the status banner and confidence guidance."
        )
    else:
        base = " ".join(lines)
        suffix = (
            " Detailed thresholds mirror the Macro Pillars tab "
            "in deterministic narrative mode."
        )
        base = (base + suffix).strip()
    while len(base) < 100:
        base += " Additional pillar commentary deferred pending fuller telemetry."
    return _truncate(base, 1000)


def build_fallback_report(ui_payload: dict) -> dict[str, Any]:
    """Deterministic AnalystReport-shaped dict from ui_payload only (no LLM)."""
    status = ui_payload.get("status") or {}
    scores = ui_payload.get("scores") or {}

    raw_rec = str(status.get("final_status") or "").strip()
    recommendation = raw_rec if raw_rec in ("GO", "CAUTION", "NO-GO") else "CAUTION"

    confidence_score = scores.get("confidence_score")
    cs_disp = _fmt_score_val(confidence_score)
    conf_clause = f"Confidence: {cs_disp}/100." if cs_disp is not None else "Confidence: N/A."

    rule_id = str(status.get("status_rule_id") or "")
    plain_reason = _FLAG_LABELS.get(rule_id, rule_id or "Refer to status context.")

    executive_summary = (
        f"Market analysis complete. Recommendation: {recommendation}. "
        f"{conf_clause} {plain_reason}"
    )
    executive_summary = _truncate(executive_summary, 400)
    while len(executive_summary) < 50:
        executive_summary += " Deterministic narrative summary."

    pillar_analysis = _pillar_analysis_from_scores(scores)

    scenarios = ui_payload.get("scenarios") or []
    if not scenarios:
        scenario_analysis = "No scenario data available."
    else:
        scen_parts: list[str] = []
        for s in scenarios:
            if not isinstance(s, dict):
                continue
            lab = str(s.get("label") or s.get("scenario_id") or "Scenario")
            opp = _fmt_score_val(s.get("opportunity_score"))
            idx = str(opp) if opp is not None else "N/A"
            scen_parts.append(f"{lab}: Relative Viability Index {idx}.")
        scenario_analysis = " ".join(scen_parts) if scen_parts else "No scenario data available."

    strategic_levers: list[str] = []
    for lev in ui_payload.get("levers") or []:
        if isinstance(lev, dict):
            label = str(lev.get("label") or "").strip()
            action = str(lev.get("action") or "").strip()
            if label or action:
                piece = f"{label} — {action}".strip(" —")
                if piece:
                    strategic_levers.append(piece)
    if not strategic_levers:
        strategic_levers = [
            "No strategic levers surfaced in this deterministic narrative snapshot."
        ]

    hidden_risks: list[str] = []
    for risk in ui_payload.get("risks") or []:
        if isinstance(risk, dict):
            label = str(risk.get("label") or "").strip()
            severity = str(risk.get("severity") or "").strip()
            if label or severity:
                piece = f"{label} — {severity}".strip(" —")
                if piece:
                    hidden_risks.append(piece)

    what_would_change: list[str] = []
    for w in ui_payload.get("what_would_change") or []:
        if isinstance(w, dict):
            cond = str(w.get("condition") or "").strip()
            impact = str(w.get("impact") or "").strip()
            if cond or impact:
                piece = f"{cond} — {impact}".strip(" —")
                if piece:
                    what_would_change.append(piece)

    confidence_note = _confidence_band_note(confidence_score)

    raw: dict[str, Any] = {
        "executive_summary": executive_summary,
        "recommendation": recommendation,
        "pillar_analysis": pillar_analysis,
        "scenario_analysis": scenario_analysis,
        "strategic_levers": strategic_levers,
        "hidden_risks": hidden_risks,
        "what_would_change": what_would_change,
        "confidence_note": confidence_note,
    }
    validate_report(raw)
    return raw


def generate_report(ui_payload: dict) -> tuple[AnalystReport, bool]:
    """
    Call Anthropic to produce an AnalystReport.
    Returns (report, llm_fallback_used). Fallback is used on APITimeoutError /
    InternalServerError during the completion request.
    """
    prompt = build_prompt(ui_payload)
    system_prompt = prompt["system_prompt"]
    user_message = prompt["user_message"]

    for attempt in (1, 2):
        try:
            try:
                response = _get_client().messages.create(
                    model=_MODEL,
                    max_tokens=_MAX_TOKENS,
                    temperature=_TEMPERATURE,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
            except anthropic.RateLimitError as e:
                raise LLMQuotaExceededError(
                    "AI report generation is temporarily unavailable "
                    "due to high demand. Scores and recommendation "
                    "are still accurate."
                ) from e
            except (anthropic.APITimeoutError, anthropic.InternalServerError) as e:
                logger.warning(
                    "LLM unavailable (%s): %s — using deterministic fallback report",
                    type(e).__name__,
                    e,
                    exc_info=True,
                )
                fb = build_fallback_report(ui_payload)
                return validate_report(fb), True
            except anthropic.APIError as exc:
                raise RuntimeError(f"Anthropic API error: {exc}") from exc

            text = response.content[0].text
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if not (text.startswith("{") and text.endswith("}")):
                raise ValueError(f"LLM returned non-JSON response: {text[:100]}")

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("LLM returned JSON that is not an object")
            # Payload-aware: if input has no WWC items, output must be []
            if not ui_payload.get("what_would_change"):
                parsed["what_would_change"] = []
            # Report Quality Gate: reject responses containing raw internal flag strings
            _RAW_FLAGS = {
                "DATA_DESERT",
                "STATUS_DATA_DESERT_CAUTION",
                "STATUS_REJECTED_DESERT",
                "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION",
                "STATUS_MONOPOLY_FORCE_CAUTION",
                "GOLDMINE_ZERO_COMPETITORS",
                "STATUS_GOLDMINE_GO",
                "STATUS_HIGH_RISK_NO_GO",
                "STATUS_DEFAULT_CAUTION",
                "REJECTED_DESERT",
            }
            _report_text = " ".join(str(v) for v in parsed.values() if isinstance(v, str)) + " " + " ".join(
                str(item)
                for v in parsed.values()
                if isinstance(v, list)
                for item in v
                if isinstance(item, str)
            )
            if any(flag in _report_text for flag in _RAW_FLAGS):
                raise ValueError("Report contains raw internal flag strings — retrying")
            return validate_report(parsed), False
        except ValueError as exc:
            if attempt == 1:
                print(f"Attempt 1 failed: {exc}, retrying...", file=sys.stderr)
                continue
            logger.warning(
                "LLM generation failed after retries (%s): %s — using deterministic fallback report",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            fb = build_fallback_report(ui_payload)
            return validate_report(fb), True
