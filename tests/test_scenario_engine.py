from pathlib import Path

from decision_engine.scenario_engine import get_scenario_scores


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = str(REPO_ROOT / "config" / "decision_logic_rules.json")


def _full_scores(**overrides: float | None) -> dict:
    base: dict = {
        "demand_score": 55.0,
        "competition_pressure_score": 55.0,
        "market_gap_score": 55.0,
        "risk_score": 55.0,
        "opportunity_score": 55.0,
        "confidence_score": 60.0,
    }
    base.update(overrides)
    return base


def test_all_three_scenarios_returned():
    scores = _full_scores()
    result = get_scenario_scores(scores, rules_path=RULES_PATH)
    assert len(result) == 3
    assert {r["scenario"] for r in result} == {"study_cafe", "grab_and_go", "third_wave_bar"}


def test_results_sorted_by_score_descending():
    scores = _full_scores()
    result = get_scenario_scores(scores, rules_path=RULES_PATH)
    vals = [float(r["scenario_score"]) for r in result]
    assert vals == sorted(vals, reverse=True)


def test_score_is_clamped():
    high = {
        "demand_score": 100.0,
        "competition_pressure_score": 100.0,
        "market_gap_score": 100.0,
        "risk_score": 100.0,
        "opportunity_score": 100.0,
        "confidence_score": 100.0,
    }
    for row in get_scenario_scores(high, rules_path=RULES_PATH):
        assert row["scenario_score"] <= 100.0

    low = {
        "demand_score": 0.0,
        "competition_pressure_score": 0.0,
        "market_gap_score": 0.0,
        "risk_score": 0.0,
        "opportunity_score": 0.0,
        "confidence_score": 0.0,
    }
    for row in get_scenario_scores(low, rules_path=RULES_PATH):
        assert row["scenario_score"] >= 0.0


def test_none_metric_skipped():
    scores = _full_scores(demand_score=None)
    result = get_scenario_scores(scores, rules_path=RULES_PATH)
    assert len(result) == 3


def test_weights_applied_excludes_none_metrics():
    scores = _full_scores(demand_score=None)
    result = get_scenario_scores(scores, rules_path=RULES_PATH)
    for row in result:
        assert "demand_score" not in row["weights_applied"]


def test_all_none_metrics_returns_zero():
    scores = {
        "demand_score": None,
        "competition_pressure_score": None,
        "market_gap_score": None,
        "risk_score": None,
        "opportunity_score": None,
        "confidence_score": None,
    }
    result = get_scenario_scores(scores, rules_path=RULES_PATH)
    for row in result:
        assert row["scenario_score"] == 0.0
        assert row["weights_applied"] == {}
