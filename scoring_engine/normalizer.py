import json
import math
from pathlib import Path


def load_thresholds(config_path=None):
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "scoring_thresholds.json"
    else:
        config_path = Path(config_path)
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(value, metric_name, thresholds):
    if value is None:
        return None

    cfg = thresholds["normalization"][metric_name]
    method = cfg["method"]
    anchors = cfg.get("anchors") or {}

    if method == "sigmoid_log10":
        x = math.log10(1 + float(value))
        midpoint = math.log10(anchors["score_50"])
        k = math.log(9) / (math.log10(anchors["score_90"]) - math.log10(anchors["score_50"]))
        raw = 1.0 / (1.0 + math.exp(-k * (x - midpoint))) * 100.0
    elif method == "sigmoid_linear":
        x = float(value)
        midpoint = anchors["score_50"]
        k = math.log(9) / (anchors["score_90"] - anchors["score_50"])
        raw = 1.0 / (1.0 + math.exp(-k * (x - midpoint))) * 100.0
    elif method == "linear_minmax":
        raw = (float(value) - cfg["min"]) / (cfg["max"] - cfg["min"]) * 100.0
    elif method == "linear_clamp":
        raw = (float(value) - cfg["min"]) / (cfg["max"] - cfg["min"]) * 100.0
    elif method == "linear_passthrough":
        raw = float(value)
    else:
        raise ValueError("Unknown normalization method: {!r}".format(method))

    if cfg.get("direction") == "higher_is_worse":
        raw = 100.0 - raw

    return max(0.0, min(100.0, raw))
