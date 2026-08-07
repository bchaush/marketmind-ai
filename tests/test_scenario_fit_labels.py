"""Relative scenario fit labels from score ordering."""

from __future__ import annotations

from ui.scenario_fit_labels import relative_scenario_fit_labels


def test_three_distinct_scores_map_to_high_middle_low() -> None:
    scenarios = [
        {"label": "A", "opportunity_score": 12.0},
        {"label": "B", "opportunity_score": 40.0},
        {"label": "C", "opportunity_score": 25.0},
    ]
    assert relative_scenario_fit_labels(scenarios) == [
        "Lowest relative fit",
        "Highest relative fit",
        "Middle relative fit",
    ]


def test_ties_use_tied_relative_fit() -> None:
    scenarios = [
        {"opportunity_score": 30.0},
        {"opportunity_score": 30.0},
        {"opportunity_score": 10.0},
    ]
    assert relative_scenario_fit_labels(scenarios) == [
        "Tied relative fit",
        "Tied relative fit",
        "Lowest relative fit",
    ]


def test_all_tied() -> None:
    scenarios = [
        {"opportunity_score": 18.0},
        {"opportunity_score": 18.0},
        {"opportunity_score": 18.0},
    ]
    assert relative_scenario_fit_labels(scenarios) == [
        "Tied relative fit",
        "Tied relative fit",
        "Tied relative fit",
    ]


def test_missing_score_insufficient_data() -> None:
    scenarios = [
        {"opportunity_score": 22.0},
        {"opportunity_score": None},
        {"opportunity_score": 11.0},
    ]
    assert relative_scenario_fit_labels(scenarios) == [
        "Highest relative fit",
        "Insufficient data",
        "Lowest relative fit",
    ]


def test_labels_follow_input_order_not_scenario_identity() -> None:
    scenarios = [
        {"scenario_id": "third_wave_bar", "opportunity_score": 5.0},
        {"scenario_id": "study_cafe", "opportunity_score": 50.0},
        {"scenario_id": "grab_and_go", "opportunity_score": 25.0},
    ]
    labels = relative_scenario_fit_labels(scenarios)
    assert labels[0] == "Lowest relative fit"
    assert labels[1] == "Highest relative fit"
    assert labels[2] == "Middle relative fit"
