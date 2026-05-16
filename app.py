from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os
import time
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from config.cta_config import get_cta_config
from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from pipeline import fetch_live_bundle
from pipeline.live_adapter import ZeroDensityLocationError
from pipeline.cache import make_cache_key
from pipeline.telemetry import log_run
from pipeline.rate_limiter import check_and_increment, remaining_today
from report_engine.llm_analyst import LLMQuotaExceededError, generate_report
from report_engine.prompt_builder import _FLAG_LABELS
from scoring_engine.scoring_engine import score
from ui.dev_payload import build_dev_payload
from ui.payload_adapter import adapt

REPO_ROOT = Path(__file__).resolve().parent

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

COOLDOWN_SECONDS = 30

STATUS_COLORS = {"GO": "#2e7d32", "CAUTION": "#e65100", "NO-GO": "#c62828"}

SCORE_KEYS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
)

GOLDEN_DEMAND = 65.4
GOLDEN_COMPETITION = 51.1
GOLDEN_FINAL_STATUS = "CAUTION"
GOLDEN_STATUS_RULE_ID = "STATUS_DATA_DESERT_CAUTION"
GOLDEN_TOLERANCE = 0.5


def _run_pipeline_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    clean_bundle = {k: v for k, v in bundle.items() if k != "_cache_meta"}
    phase2 = score(clean_bundle)
    scores = {k: phase2[k] for k in SCORE_KEYS}
    flags = list(phase2["flags"])
    raw = build_analyst_payload(scores, flags)
    validated = validate_analyst_payload(raw)
    return adapt(validated)


def _check_golden_sync(ui_payload: dict[str, Any]) -> None:
    scores = ui_payload.get("scores") or {}
    status = ui_payload.get("status") or {}

    demand = scores.get("demand_score")
    if demand is not None and abs(float(demand) - GOLDEN_DEMAND) > GOLDEN_TOLERANCE:
        st.warning(
            f"Golden sync drift: demand_score={demand}, expected ≈{GOLDEN_DEMAND} "
            f"(±{GOLDEN_TOLERANCE})"
        )

    competition = scores.get("competition_pressure_score")
    if competition is not None and abs(float(competition) - GOLDEN_COMPETITION) > GOLDEN_TOLERANCE:
        st.warning(
            f"Golden sync drift: competition_pressure_score={competition}, "
            f"expected ≈{GOLDEN_COMPETITION} (±{GOLDEN_TOLERANCE})"
        )

    final_status = status.get("final_status")
    if final_status != GOLDEN_FINAL_STATUS:
        st.warning(
            f"Golden sync drift: final_status={final_status!r}, "
            f"expected {GOLDEN_FINAL_STATUS!r}"
        )

    status_rule_id = status.get("status_rule_id")
    if status_rule_id != GOLDEN_STATUS_RULE_ID:
        st.warning(
            f"Golden sync drift: status_rule_id={status_rule_id!r}, "
            f"expected {GOLDEN_STATUS_RULE_ID!r}"
        )


def _fmt_score(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{round(float(value), 1)}"


def _translate_wwc_display(text: str) -> str:
    """Map WWC UI fragments through _FLAG_LABELS (handles \"To GO:\" / \"To NO-GO:\" lines)."""
    if not text.strip():
        return text
    parts_out: list[str] = []
    for part in text.split(" | "):
        p = part.strip()
        if not p:
            continue
        if p in _FLAG_LABELS:
            parts_out.append(_FLAG_LABELS[p])
            continue
        translated: str | None = None
        for prefix in ("To GO:", "To NO-GO:"):
            if p.startswith(prefix):
                tail = p[len(prefix) :].strip()
                key_candidate = tail.lower().replace(" ", "_").upper()
                translated = _FLAG_LABELS.get(key_candidate)
                break
        parts_out.append(translated if translated is not None else p)
    return " | ".join(parts_out)


def _build_dev_payload(
    ui_payload: Mapping[str, Any],
    live_bundle: Mapping[str, Any],
    cache_key: str,
) -> dict[str, Any]:
    """Developer View JSON source; delegated to ui.dev_payload (pure helper)."""
    return build_dev_payload(ui_payload, live_bundle, cache_key, repo_root=REPO_ROOT)


st.set_page_config(page_title="MarketMind AI", page_icon="🧠", layout="wide")

with st.sidebar:
    st.markdown("**🧠 MarketMind AI**")
    st.caption("Boston Market Intelligence")
    st.markdown("📍 Default area: Inman Square (42.3736, -71.1097) — stable Census coverage")
    st.markdown("☕ Coffee Shop (default)")
    lat = st.number_input("Latitude", value=42.3736, format="%.4f")
    lng = st.number_input("Longitude", value=-71.1097, format="%.4f")
    radius_miles = st.number_input("Radius (miles)", value=1.0, min_value=0.01, format="%.2f")
    business_type = st.text_input("Business type", value="coffee_shop")

    if st.button("Run Analysis", type="primary"):
        last_run = st.session_state.get("last_run_at", 0)
        elapsed = time.time() - float(last_run or 0)
        if last_run and elapsed < COOLDOWN_SECONDS:
            remaining_cd = max(1, int(COOLDOWN_SECONDS - elapsed))
            st.warning(
                f"Please wait {remaining_cd} seconds before running another analysis."
            )
            st.stop()
        allowed, _remaining_budget = check_and_increment()
        if not allowed:
            st.error(
                "Daily analysis limit reached. "
                "MarketMind AI runs on live data APIs with "
                "daily request caps to ensure service quality. "
                "Capacity resets at midnight. "
                "Check back tomorrow or contact us for "
                "priority access."
            )
            st.stop()
        try:
            # MVP: all three status lines render before fetch_live_bundle() blocks; they appear
            # together, not as a timed sequence — acceptable UX limitation (do not split adapter).
            with st.status("Analysis in progress", expanded=True) as status:
                status.write("Scanning competitor landscape...")
                status.write("Pulling demographic data...")
                status.write("Building market profile...")
                bundle = fetch_live_bundle(
                    lat,
                    lng,
                    business_type.strip() or "coffee_shop",
                    radius_miles=radius_miles,
                )
            status.update(label="Analysis complete", state="complete", expanded=False)
            st.session_state["live_bundle"] = bundle
            st.session_state["ui_payload"] = _run_pipeline_from_bundle(bundle)
            _tel_pl = st.session_state["ui_payload"]
            log_run(
                lat,
                lng,
                _tel_pl["status"]["final_status"],
                _tel_pl["scores"]["confidence_score"],
            )
            if DEV_MODE:
                _check_golden_sync(st.session_state["ui_payload"])
            st.session_state.pop("analyst_report", None)
            st.session_state.pop("report_error", None)
            st.session_state.pop("report_llm_fallback", None)
            st.session_state.pop("report_quota_exceeded", None)
            st.session_state["last_run_at"] = time.time()
        except ZeroDensityLocationError as e:
            st.warning(str(e))
        except ValueError as e:
            st.error(str(e))

    if st.button("Refresh Data"):
        st.session_state.pop("ui_payload", None)
        st.session_state.pop("live_bundle", None)
        st.session_state.pop("analyst_report", None)
        st.session_state.pop("report_error", None)
        st.session_state.pop("report_llm_fallback", None)
        st.session_state.pop("report_quota_exceeded", None)
        st.rerun()

    _live_bundle_sb = st.session_state.get("live_bundle")
    if isinstance(_live_bundle_sb, dict) and _live_bundle_sb:
        _cache_meta_sb = _live_bundle_sb.get("_cache_meta") or {}
        _was_cached = _cache_meta_sb.get("cache_hit", False)
        _written_at = _cache_meta_sb.get("written_at", "unknown")
        if _was_cached:
            st.sidebar.success(f"📦 Cached data\n\nWritten: {_written_at}")
        else:
            st.sidebar.success("🟢 Live data")
        if DEV_MODE:
            st.sidebar.caption(f"Cache key: {_cache_meta_sb.get('key', 'unknown')}")

    if DEV_MODE:
        st.sidebar.caption(f"API budget remaining today: {remaining_today()}")
if "ui_payload" not in st.session_state:
    st.info("Configure coordinates in the sidebar and click **Run Analysis** to load live market data.")
    st.stop()

ui_payload = st.session_state["ui_payload"]

if "analyst_report" not in st.session_state:
    with st.spinner("Synthesizing market intelligence — generating analyst report..."):
        try:
            report, used_fallback = generate_report(st.session_state["ui_payload"])
            st.session_state["analyst_report"] = report.model_dump()
            st.session_state["report_llm_fallback"] = used_fallback
            st.session_state["report_error"] = None
            st.session_state["report_quota_exceeded"] = False
        except LLMQuotaExceededError:
            st.session_state["analyst_report"] = None
            st.session_state["report_llm_fallback"] = False
            st.session_state["report_error"] = None
            st.session_state["report_quota_exceeded"] = True
            st.warning(
                "⚠️ AI narrative report temporarily unavailable — "
                "high demand on the analysis service. "
                "Your market scores and GO / CAUTION / NO-GO "
                "recommendation above are fully accurate and "
                "based on live data. Try refreshing in a few minutes."
            )
        except Exception as e:
            st.session_state["analyst_report"] = None
            st.session_state["report_llm_fallback"] = False
            st.session_state["report_quota_exceeded"] = False
            st.session_state["report_error"] = str(e)

status = ui_payload.get("status") or {}
scores = ui_payload.get("scores") or {}
flags = ui_payload.get("flags") or []
null_adjustments = ui_payload.get("null_adjustments") or []
tradeoffs = ui_payload.get("tradeoffs") or []
levers = ui_payload.get("levers") or []
risks = ui_payload.get("risks") or []
what_would_change = ui_payload.get("what_would_change") or []
scenarios = ui_payload.get("scenarios") or []
business_profile = ui_payload.get("business_profile") or {}

final_status = str(status.get("final_status") or "")
status_rule_id = str(status.get("status_rule_id") or "")
banner_color = STATUS_COLORS.get(final_status, STATUS_COLORS["CAUTION"])

st.markdown(
    f"""
    <div style="
        background-color: {banner_color};
        color: white;
        font-weight: bold;
        padding: 20px;
        border-radius: 8px;
        font-size: 28px;
        text-align: center;
        width: 100%;
    ">{final_status}</div>
    """,
    unsafe_allow_html=True,
)

st.caption(_FLAG_LABELS.get(status_rule_id, status_rule_id))

tab_macro, tab_scenarios, tab_risk = st.tabs(
    ["📊 Pillars", "🧩 Scenarios", "⚠️ Risks"]
)

with tab_macro:
    row1 = st.columns(3)
    row1[0].metric("Demand Score", _fmt_score(scores.get("demand_score")))
    row1[1].metric("Competition Pressure", _fmt_score(scores.get("competition_pressure_score")))
    row1[2].metric("Market Gap", _fmt_score(scores.get("market_gap_score")))

    row2 = st.columns(3)
    row2[0].metric("Risk Score", _fmt_score(scores.get("risk_score")))
    row2[1].metric("Opportunity Score", _fmt_score(scores.get("opportunity_score")))
    row2[2].metric("Confidence Score", _fmt_score(scores.get("confidence_score")))

    _conf_raw = scores.get("confidence_score")
    if _conf_raw is not None:
        _conf = float(_conf_raw)
        if _conf >= 75:
            _conf_label = "High confidence — suitable for investment screening"
        elif _conf >= 45:
            _conf_label = "Moderate confidence — directional insight, verify before committing"
        else:
            _conf_label = "Low confidence — suitable for initial screening only, not investment decisions"
        st.caption(_conf_label)

    if "DATA_DESERT" in flags:
        st.warning(
            "⚠️ Data Desert active — confidence capped at 74. "
            "Three or more metrics are missing."
        )

    for adjustment in null_adjustments:
        st.caption(adjustment)

with tab_scenarios:
    st.subheader("Scenarios")
    st.caption("Relative Viability Index — higher score = stronger strategic fit for this location")
    if scenarios:
        scenario_cols = st.columns(len(scenarios))
        for col, scenario in zip(scenario_cols, scenarios):
            label = str(scenario.get("label") or scenario.get("scenario_id") or "Scenario")
            opp = scenario.get("opportunity_score")
            value = "N/A" if opp is None else f"{round(float(opp), 1)}"
            if opp is None:
                band = "Insufficient data"
            elif float(opp) >= 20:
                band = "Strong fit"
            elif float(opp) >= 10:
                band = "Moderate fit"
            else:
                band = "Insufficient data"
            col.metric(label, value)
            col.caption(band)
    else:
        st.caption("No scenarios available.")

    st.subheader("Tradeoffs")
    if tradeoffs:
        for item in tradeoffs:
            label = str(item.get("label") or "")
            description = str(item.get("description") or "")
            st.info(f"**{label}** — {description}")
    else:
        st.caption("No trade-off tensions detected.")

    st.subheader("Levers")
    for item in levers:
        label = str(item.get("label") or "")
        action = str(item.get("action") or "")
        st.success(f"**{label}** — {action}")

with tab_risk:
    st.subheader("Risks")
    for item in risks:
        label = str(item.get("label") or "")
        severity = str(item.get("severity") or "")
        st.error(f"**{label}** — {severity}")

    st.subheader("What Would Change")
    if what_would_change:
        for item in what_would_change:
            condition = _translate_wwc_display(str(item.get("condition") or ""))
            impact = _translate_wwc_display(str(item.get("impact") or ""))
            st.warning(f"**{condition}** — {impact}")
    else:
        st.caption("No threshold flip conditions triggered.")

st.divider()
st.subheader("🧠 AI Analyst Report")

if st.session_state.get("report_llm_fallback"):
    st.info(
        "AI report generated from deterministic analysis — "
        "live AI narrative temporarily unavailable. "
        "All scores and recommendations are accurate."
    )

if st.session_state.get("analyst_report"):
    report = st.session_state["analyst_report"]
    with st.expander("Executive Summary", expanded=True):
        st.write(report["executive_summary"])
    with st.expander("Pillar Analysis"):
        st.write(report["pillar_analysis"])
    with st.expander("Scenario Analysis"):
        st.write(report["scenario_analysis"])
    with st.expander("Strategic Levers"):
        for item in report["strategic_levers"]:
            st.success(item)
    with st.expander("Hidden Risks"):
        for item in report["hidden_risks"]:
            st.error(item)
    with st.expander("What Would Change"):
        if report["what_would_change"]:
            for item in report["what_would_change"]:
                st.warning(_translate_wwc_display(str(item)))
        else:
            st.caption("No threshold flip conditions in current data.")
    with st.expander("Confidence Note"):
        st.write(report["confidence_note"])
elif st.session_state.get("report_error"):
    st.error(f"Report generation failed: {st.session_state['report_error']}")
elif st.session_state.get("report_quota_exceeded"):
    pass
else:
    st.caption("Report not available.")

st.divider()
_cta = get_cta_config()
st.markdown(f"**{_cta['headline']}**")
st.caption(_cta["subtext"])
st.link_button(_cta["link_label"], _cta["link_url"])
if _cta["secondary_label"] is not None:
    st.link_button(_cta["secondary_label"], _cta["secondary_url"])
st.caption(
    "🔒 Search coordinates are anonymized to 3 decimal places. "
    "No personal data is stored or transmitted."
)

if os.getenv("DEV_MODE", "false").lower() == "true":
    with st.expander("🔧 Developer View", expanded=False):
        st.caption("Visible only when DEV_MODE=true. Never shown in production.")
        st.json(
            _build_dev_payload(
                ui_payload,
                st.session_state.get("live_bundle") or {},
                make_cache_key(
                    lat,
                    lng,
                    business_type.strip() or "coffee_shop",
                    radius_miles,
                ),
            )
        )
        st.caption(
            "Scoring weights loaded from config/scoring_weights.json. "
            "No API keys, raw responses, or filesystem paths are included in this view."
        )
