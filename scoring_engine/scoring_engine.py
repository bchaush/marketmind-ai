import json
from pathlib import Path

from scoring_engine.normalizer import load_thresholds, normalize


def _load_weights():
    path = Path(__file__).resolve().parents[1] / "config" / "scoring_weights.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _calculate_weighted_score(metrics, weights):
    remaining = {k: metrics[k] for k in weights if k in metrics and metrics[k] is not None}
    if not remaining:
        return None
    w_sum = sum(weights[k] for k in remaining)
    if w_sum == 0.0:
        return None
    total = 0.0
    for k in remaining:
        total += float(metrics[k]) * (float(weights[k]) / w_sum)
    return total


def _reinvert_for_pressure_or_risk(v):
    if v is None:
        return None
    return 100.0 - float(v)


def score(bundle):
    pop_total = bundle["demographic_data"]["pop_total"]
    age_22_34_count = bundle["demographic_data"]["age_22_34_count"]
    college_student_population_pct = bundle["demographic_data"]["college_student_population_pct"]
    median_household_income = bundle["demographic_data"]["median_household_income"]
    rent_to_income_ratio = bundle["demographic_data"]["rent_to_income_ratio"]
    total_count = bundle["competitor_data"]["summary"]["total_count"]
    avg_rating = bundle["competitor_data"]["summary"]["avg_rating"]
    top_3_review_share_pct = bundle["competitor_data"]["summary"]["top_3_review_share_pct"]

    if pop_total is None or pop_total == 0:
        return {
            "demand_score": None,
            "competition_pressure_score": None,
            "market_gap_score": None,
            "risk_score": None,
            "opportunity_score": None,
            "confidence_score": 0.0,
            "null_count": 8,
            "flags": ["REJECTED_DESERT"],
            "status": "REJECTED_DESERT",
        }

    thresholds = load_thresholds()
    n_pop_total = normalize(pop_total, "pop_total", thresholds)
    n_age_22_34_count = normalize(age_22_34_count, "age_22_34_count", thresholds)
    n_college_student_pct = normalize(college_student_population_pct, "college_student_population_pct", thresholds)
    n_median_income = normalize(median_household_income, "median_household_income", thresholds)
    n_rent_to_income = normalize(rent_to_income_ratio, "rent_to_income_ratio", thresholds)
    n_total_count = normalize(total_count, "total_count", thresholds)
    n_avg_rating = normalize(avg_rating, "avg_rating", thresholds)
    n_top_3_share = normalize(top_3_review_share_pct, "top_3_review_share_pct", thresholds)

    normalized_values = [
        n_pop_total,
        n_age_22_34_count,
        n_college_student_pct,
        n_median_income,
        n_rent_to_income,
        n_total_count,
        n_avg_rating,
        n_top_3_share,
    ]
    null_count = sum(1 for v in normalized_values if v is None)

    weights = _load_weights()

    demand_score = _calculate_weighted_score(
        {
            "pop_total": n_pop_total,
            "age_22_34_count": n_age_22_34_count,
            "college_student_population_pct": n_college_student_pct,
        },
        weights["demand_score"],
    )

    p_total_count = _reinvert_for_pressure_or_risk(n_total_count)
    p_avg_rating = _reinvert_for_pressure_or_risk(n_avg_rating)
    p_top_3_share = _reinvert_for_pressure_or_risk(n_top_3_share)

    competition_pressure_score = _calculate_weighted_score(
        {
            "total_count": p_total_count,
            "avg_rating": p_avg_rating,
            "top_3_review_share_pct": p_top_3_share,
        },
        weights["competition_pressure_score"],
    )

    if demand_score is None or competition_pressure_score is None:
        market_gap_score = None
    else:
        supply_proxy = (
            100.0 - float(competition_pressure_score)
            if competition_pressure_score is not None
            else None
        )
        market_gap_score = _calculate_weighted_score(
            {
                "demand_proxy": demand_score,
                "supply_proxy": supply_proxy,
            },
            weights["market_gap_score"],
        )

    r_rent = _reinvert_for_pressure_or_risk(n_rent_to_income)
    r_median = _reinvert_for_pressure_or_risk(n_median_income)
    r_top_3 = _reinvert_for_pressure_or_risk(n_top_3_share)
    r_avg = _reinvert_for_pressure_or_risk(n_avg_rating)

    risk_score = _calculate_weighted_score(
        {
            "rent_to_income_ratio": r_rent,
            "median_household_income": r_median,
            "top_3_review_share_pct": r_top_3,
            "avg_rating": r_avg,
        },
        weights["risk_score"],
    )

    if demand_score is None or market_gap_score is None or competition_pressure_score is None:
        opportunity_score = None
    else:
        comp_inverted = 100.0 - float(competition_pressure_score)
        opportunity_score = _calculate_weighted_score(
            {
                "demand": demand_score,
                "market_gap": market_gap_score,
                "competition_pressure_inverted": comp_inverted,
            },
            weights["opportunity_score"],
        )

    base = float(bundle["demographic_data"]["confidence_score"])
    penalty = float(null_count) * float(thresholds["null_handling"]["confidence_penalty_per_null"])
    geography_level = bundle["demographic_data"]["geography_level"]
    fidelity = float(thresholds["geography_fidelity"][geography_level])
    confidence_score = (base - penalty) * (fidelity / 100.0)
    if null_count >= 3:
        confidence_score = max(
            confidence_score,
            float(thresholds["confidence_floors"]["data_desert"]),
        )
    confidence_score = max(0.0, min(100.0, confidence_score))

    flags = []

    if top_3_review_share_pct > 60:
        flags.append("CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION")
        if risk_score is not None:
            risk_score = min(100.0, float(risk_score) + 15.0)

    if total_count == 0 and pop_total > 2500:
        flags.append("GOLDMINE_ZERO_COMPETITORS")
        opportunity_score = 100.0
        market_gap_score = max(float(market_gap_score or 0.0), 85.0)

    if null_count >= 3:
        flags.append("DATA_DESERT")
        confidence_score = max(
            confidence_score,
            float(thresholds["confidence_floors"]["data_desert"]),
        )
        confidence_score = min(confidence_score, 74.0)

    if opportunity_score is None:
        status = "INSUFFICIENT_DATA"
    elif opportunity_score >= 65:
        status = "GO"
    elif opportunity_score >= 40:
        status = "CAUTION"
    else:
        status = "DO_NOT_ENTER"

    if "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION" in flags:
        if status == "GO":
            status = "CAUTION"

    return {
        "demand_score": demand_score,
        "competition_pressure_score": competition_pressure_score,
        "market_gap_score": market_gap_score,
        "risk_score": risk_score,
        "opportunity_score": opportunity_score,
        "confidence_score": confidence_score,
        "null_count": null_count,
        "flags": flags,
        "status": status,
    }
