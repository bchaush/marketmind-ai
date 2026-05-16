from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from report_engine.llm_analyst import (
    LLMQuotaExceededError,
    build_fallback_report,
)
from report_engine.report_schema import validate_report
from scoring_engine.scoring_engine import score
from ui.payload_adapter import adapt

REPO_ROOT = Path(__file__).resolve().parents[1]
MOCK_PATH = REPO_ROOT / "mock_data" / "mock_boston_data.json"

SCORE_KEYS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
)

REPORT_KEYS = frozenset(
    {
        "executive_summary",
        "recommendation",
        "pillar_analysis",
        "scenario_analysis",
        "strategic_levers",
        "hidden_risks",
        "what_would_change",
        "confidence_note",
    }
)


def _ui_payload_from_mock() -> dict:
    bundle = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    phase2 = score(bundle)
    scores = {k: phase2[k] for k in SCORE_KEYS}
    flags = list(phase2["flags"])
    raw = build_analyst_payload(scores, flags)
    validated = validate_analyst_payload(raw)
    return adapt(validated)


def test_fallback_report_structure():
    ui = _ui_payload_from_mock()
    raw = build_fallback_report(ui)
    model = validate_report(raw)
    dumped = model.model_dump()
    assert set(dumped.keys()) == REPORT_KEYS


def test_fallback_report_null_scores():
    ui = {
        "status": {
            "final_status": "NO-GO",
            "status_rule_id": "STATUS_REJECTED_DESERT",
        },
        "scores": {k: None for k in SCORE_KEYS},
        "scenarios": [],
        "levers": [],
        "risks": [],
        "what_would_change": [],
    }
    raw = build_fallback_report(ui)
    model = validate_report(raw)
    assert model.recommendation == "NO-GO"
    assert "Insufficient data" in model.pillar_analysis


def test_fallback_recommendation_matches_status():
    for final_status in ("GO", "CAUTION", "NO-GO"):
        ui = {
            "status": {
                "final_status": final_status,
                "status_rule_id": "STATUS_DEFAULT_CAUTION",
            },
            "scores": {
                "demand_score": 55.0,
                "competition_pressure_score": 55.0,
                "market_gap_score": 55.0,
                "risk_score": 55.0,
                "opportunity_score": 55.0,
                "confidence_score": 60.0,
            },
            "scenarios": [{"label": "Test Scenario", "opportunity_score": 15.0}],
            "levers": [{"label": "Lever A", "action": "Monitor pricing"}],
            "risks": [{"label": "Risk A", "severity": "medium"}],
            "what_would_change": [],
        }
        raw = build_fallback_report(ui)
        model = validate_report(raw)
        assert model.recommendation == final_status


def test_llm_quota_error_raises_custom_exception():
    ui = _ui_payload_from_mock()
    resp = MagicMock()
    resp.status_code = 429
    err = anthropic.RateLimitError("Too Many Requests", response=resp, body=None)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = err

    import report_engine.llm_analyst as llm_analyst_mod

    with patch.object(llm_analyst_mod, "_get_client", return_value=mock_client):
        with pytest.raises(LLMQuotaExceededError):
            llm_analyst_mod.generate_report(ui)
