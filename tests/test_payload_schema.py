import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import AnalystPayload, validate_analyst_payload
from scoring_engine.scoring_engine import score


REPO_ROOT = Path(__file__).resolve().parents[1]


def _scores(**kwargs):
    base = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    base.update(kwargs)
    return base


def test_bu_golden_validates():
    mock_path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    bundle = json.loads(mock_path.read_text(encoding="utf-8"))
    phase2 = score(bundle)
    score_keys = (
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    )
    scores = {k: phase2[k] for k in score_keys}
    flags = list(phase2["flags"])
    raw = build_analyst_payload(scores, flags)
    result = validate_analyst_payload(raw)
    assert isinstance(result, AnalystPayload)


def test_invalid_final_status_raises():
    mock_path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    bundle = json.loads(mock_path.read_text(encoding="utf-8"))
    phase2 = score(bundle)
    score_keys = (
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    )
    scores = {k: phase2[k] for k in score_keys}
    flags = list(phase2["flags"])
    payload = copy.deepcopy(build_analyst_payload(scores, flags))
    payload["executive_decision"]["final_status"] = "MAYBE"
    with pytest.raises(ValidationError):
        validate_analyst_payload(payload)


def test_missing_key_raises():
    mock_path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    bundle = json.loads(mock_path.read_text(encoding="utf-8"))
    phase2 = score(bundle)
    score_keys = (
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    )
    scores = {k: phase2[k] for k in score_keys}
    flags = list(phase2["flags"])
    payload = copy.deepcopy(build_analyst_payload(scores, flags))
    del payload["executive_decision"]
    with pytest.raises(ValidationError):
        validate_analyst_payload(payload)


def test_model_dump_json_is_valid():
    mock_path = REPO_ROOT / "mock_data" / "mock_boston_data.json"
    bundle = json.loads(mock_path.read_text(encoding="utf-8"))
    phase2 = score(bundle)
    score_keys = (
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    )
    scores = {k: phase2[k] for k in score_keys}
    flags = list(phase2["flags"])
    raw = build_analyst_payload(scores, flags)
    result = validate_analyst_payload(raw)
    dumped = result.model_dump_json()
    roundtrip = json.loads(dumped)
    expected_top = {
        "metadata",
        "executive_decision",
        "trade_offs",
        "risks",
        "levers",
        "what_would_change",
        "scenario_scores",
        "evidence",
    }
    assert set(roundtrip.keys()) == expected_top


def test_all_golden_cases_validate():
    cases = [
        (
            _scores(
                demand_score=72.0,
                competition_pressure_score=88.0,
                market_gap_score=28.0,
                risk_score=74.0,
                opportunity_score=38.0,
                confidence_score=80.0,
            ),
            ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"],
        ),
        (
            _scores(
                demand_score=78.0,
                competition_pressure_score=0.0,
                market_gap_score=95.0,
                risk_score=35.0,
                opportunity_score=100.0,
                confidence_score=85.0,
            ),
            ["GOLDMINE_ZERO_COMPETITORS"],
        ),
        (
            _scores(
                demand_score=82.0,
                competition_pressure_score=30.0,
                market_gap_score=75.0,
                risk_score=87.0,
                opportunity_score=68.0,
                confidence_score=78.0,
            ),
            [],
        ),
        (
            _scores(
                demand_score=55.0,
                competition_pressure_score=40.0,
                market_gap_score=None,
                risk_score=None,
                opportunity_score=None,
                confidence_score=44.0,
            ),
            ["DATA_DESERT"],
        ),
        (
            _scores(
                demand_score=38.0,
                competition_pressure_score=32.0,
                market_gap_score=42.0,
                risk_score=50.0,
                opportunity_score=40.0,
                confidence_score=65.0,
            ),
            [],
        ),
    ]
    for scores, flags in cases:
        raw = build_analyst_payload(scores, flags)
        out = validate_analyst_payload(raw)
        assert isinstance(out, AnalystPayload)
