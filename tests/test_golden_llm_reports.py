from __future__ import annotations

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from report_engine.prompt_builder import build_prompt
from tests.test_golden_snapshots import _scores
from ui.payload_adapter import adapt

_RAW_FLAGS: frozenset[str] = frozenset(
    {
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
)


def _prompt_and_ui(scores: dict, flags: list[str]) -> tuple[dict[str, str], dict]:
    raw = build_analyst_payload(scores, flags)
    validated = validate_analyst_payload(raw)
    ui_payload = adapt(validated)
    return build_prompt(ui_payload), ui_payload


def _assert_prompt_quality(prompt: dict[str, str], ui_payload: dict, *, expected_final_status: str) -> None:
    assert set(prompt.keys()) == {"system_prompt", "user_message"}

    blob = f"{prompt['system_prompt']}\n{prompt['user_message']}"
    for flag in _RAW_FLAGS:
        assert flag not in blob

    user_message = prompt["user_message"]
    assert f"<final_status>{expected_final_status}</final_status>" in user_message

    wwc = ui_payload.get("what_would_change") or []
    if not wwc:
        start = user_message.find("<what_would_change>")
        assert start != -1
        end = user_message.find("</what_would_change>", start)
        assert end != -1
        section = user_message[start:end]
        assert "<!-- empty -->" in section


def test_golden_llm_prompt_monopoly_market():
    scores = _scores(
        demand_score=72.0,
        competition_pressure_score=88.0,
        market_gap_score=28.0,
        risk_score=74.0,
        opportunity_score=38.0,
        confidence_score=80.0,
    )
    flags = ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"]
    prompt, ui = _prompt_and_ui(scores, flags)
    _assert_prompt_quality(prompt, ui, expected_final_status="CAUTION")


def test_golden_llm_prompt_goldmine():
    scores = _scores(
        demand_score=78.0,
        competition_pressure_score=0.0,
        market_gap_score=95.0,
        risk_score=35.0,
        opportunity_score=100.0,
        confidence_score=85.0,
    )
    flags = ["GOLDMINE_ZERO_COMPETITORS"]
    prompt, ui = _prompt_and_ui(scores, flags)
    _assert_prompt_quality(prompt, ui, expected_final_status="GO")


def test_golden_llm_prompt_seaport_paradox():
    scores = _scores(
        demand_score=82.0,
        competition_pressure_score=30.0,
        market_gap_score=75.0,
        risk_score=87.0,
        opportunity_score=68.0,
        confidence_score=78.0,
    )
    flags: list[str] = []
    prompt, ui = _prompt_and_ui(scores, flags)
    _assert_prompt_quality(prompt, ui, expected_final_status="NO-GO")


def test_golden_llm_prompt_data_desert():
    scores = _scores(
        demand_score=55.0,
        competition_pressure_score=40.0,
        market_gap_score=None,
        risk_score=None,
        opportunity_score=None,
        confidence_score=44.0,
    )
    flags = ["DATA_DESERT"]
    prompt, ui = _prompt_and_ui(scores, flags)
    _assert_prompt_quality(prompt, ui, expected_final_status="CAUTION")


def test_golden_llm_prompt_undersized_market():
    scores = _scores(
        demand_score=38.0,
        competition_pressure_score=32.0,
        market_gap_score=42.0,
        risk_score=50.0,
        opportunity_score=40.0,
        confidence_score=65.0,
    )
    flags: list[str] = []
    prompt, ui = _prompt_and_ui(scores, flags)
    _assert_prompt_quality(prompt, ui, expected_final_status="CAUTION")
