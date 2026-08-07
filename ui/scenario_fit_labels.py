"""Relative scenario fit labels for UI display (no score recalculation)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence


def relative_scenario_fit_labels(
    scenarios: Sequence[Mapping[str, Any]],
    *,
    score_key: str = "opportunity_score",
) -> list[str]:
    """
    Label each scenario from numeric ordering of its display score.

    Highest / Middle / Lowest are assigned only for unique score values.
    Tied numeric values share \"Tied relative fit\" rather than a forced order.
    Missing scores are labeled \"Insufficient data\".
    """
    n = len(scenarios)
    labels = ["Insufficient data"] * n
    by_score: dict[float, list[int]] = defaultdict(list)

    for i, scenario in enumerate(scenarios):
        raw = scenario.get(score_key)
        if raw is None:
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        by_score[score].append(i)

    if not by_score:
        return labels

    unique_desc = sorted(by_score.keys(), reverse=True)
    rank_words: dict[float, str] = {}

    for rank, score in enumerate(unique_desc):
        if len(by_score[score]) > 1:
            rank_words[score] = "Tied relative fit"
            continue
        if rank == 0:
            rank_words[score] = "Highest relative fit"
        elif rank == len(unique_desc) - 1:
            rank_words[score] = "Lowest relative fit"
        else:
            rank_words[score] = "Middle relative fit"

    for score, indices in by_score.items():
        word = rank_words[score]
        for i in indices:
            labels[i] = word
    return labels
