from pathlib import Path

from scoring_engine.normalizer import load_thresholds, normalize


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_1_none_input_returns_none():
    thresholds = load_thresholds(REPO_ROOT / "config" / "scoring_thresholds.json")
    assert normalize(None, "pop_total", thresholds) is None


def test_2_pop_total_sigmoid_log10_score_50_anchor():
    thresholds = load_thresholds(REPO_ROOT / "config" / "scoring_thresholds.json")
    score = normalize(1000, "pop_total", thresholds)
    assert 45 <= score <= 55


def test_3_total_count_linear_minmax_higher_is_worse():
    thresholds = load_thresholds(REPO_ROOT / "config" / "scoring_thresholds.json")
    assert normalize(0, "total_count", thresholds) == 100.0
    assert normalize(40, "total_count", thresholds) == 0.0


def test_4_avg_rating_linear_clamp_higher_is_worse():
    thresholds = load_thresholds(REPO_ROOT / "config" / "scoring_thresholds.json")
    assert normalize(3.0, "avg_rating", thresholds) == 100.0
    assert normalize(5.0, "avg_rating", thresholds) == 0.0


def test_5_rent_to_income_sigmoid_linear_higher_is_worse():
    thresholds = load_thresholds(REPO_ROOT / "config" / "scoring_thresholds.json")
    score = normalize(0.30, "rent_to_income_ratio", thresholds)
    assert 45 <= score <= 55


def test_6_unknown_method_raises_value_error():
    thresholds = {
        "normalization": {
            "fake_metric": {
                "method": "unknown_method_xyz",
                "anchors": {"score_50": 1, "score_90": 2},
            }
        }
    }
    try:
        normalize(1.0, "fake_metric", thresholds)
    except ValueError:
        return
    raise AssertionError("Expected ValueError")
