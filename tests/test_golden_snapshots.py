from decision_engine.analyst_payload import build_analyst_payload


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


def test_golden_monopoly_market():
    scores = _scores(
        demand_score=72.0,
        competition_pressure_score=88.0,
        market_gap_score=28.0,
        risk_score=74.0,
        opportunity_score=38.0,
        confidence_score=80.0,
    )
    flags = ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"]
    payload = build_analyst_payload(scores, flags)
    assert payload["executive_decision"]["final_status"] == "CAUTION"
    assert payload["executive_decision"]["status_rule_id"] == "STATUS_MONOPOLY_FORCE_CAUTION"
    assert any(r["rule_id"] == "RISK_MONOPOLY_CONCENTRATION" for r in payload["risks"])
    assert any(r["rule_id"] == "TRADEOFF_HIGH_DEMAND_HIGH_COMPETITION" for r in payload["trade_offs"])


def test_golden_goldmine_market():
    scores = _scores(
        demand_score=78.0,
        competition_pressure_score=0.0,
        market_gap_score=95.0,
        risk_score=35.0,
        opportunity_score=100.0,
        confidence_score=85.0,
    )
    flags = ["GOLDMINE_ZERO_COMPETITORS"]
    payload = build_analyst_payload(scores, flags)
    assert payload["executive_decision"]["final_status"] == "GO"
    assert payload["executive_decision"]["status_rule_id"] == "STATUS_GOLDMINE_GO"
    assert any(r["rule_id"] == "LEVER_FIRST_MOVER" for r in payload["levers"])


def test_golden_seaport_paradox():
    scores = _scores(
        demand_score=82.0,
        competition_pressure_score=30.0,
        market_gap_score=75.0,
        risk_score=87.0,
        opportunity_score=68.0,
        confidence_score=78.0,
    )
    flags = []
    payload = build_analyst_payload(scores, flags)
    assert payload["executive_decision"]["final_status"] == "NO-GO"
    assert payload["executive_decision"]["status_rule_id"] == "STATUS_HIGH_RISK_NO_GO"
    assert any(r["rule_id"] == "LEVER_REDUCE_FOOTPRINT" for r in payload["levers"])
    assert any(r["rule_id"] == "RISK_HIGH_RENT_BURDEN" for r in payload["risks"])


def test_golden_data_desert():
    scores = _scores(
        demand_score=55.0,
        competition_pressure_score=40.0,
        market_gap_score=None,
        risk_score=None,
        opportunity_score=None,
        confidence_score=44.0,
    )
    flags = ["DATA_DESERT"]
    payload = build_analyst_payload(scores, flags)
    assert payload["executive_decision"]["final_status"] == "CAUTION"
    assert payload["executive_decision"]["status_rule_id"] == "STATUS_DATA_DESERT_CAUTION"
    assert any(r["rule_id"] == "RISK_DATA_DESERT" for r in payload["risks"])
    assert any(r["rule_id"] == "RISK_LOW_CONFIDENCE_FLOOR" for r in payload["risks"])


def test_golden_undersized_market():
    scores = _scores(
        demand_score=38.0,
        competition_pressure_score=32.0,
        market_gap_score=42.0,
        risk_score=50.0,
        opportunity_score=40.0,
        confidence_score=65.0,
    )
    flags = []
    payload = build_analyst_payload(scores, flags)
    assert payload["executive_decision"]["final_status"] == "CAUTION"
    assert payload["executive_decision"]["status_rule_id"] == "STATUS_DEFAULT_CAUTION"
    assert any(r["rule_id"] == "TRADEOFF_LOW_DEMAND_LOW_COMPETITION" for r in payload["trade_offs"])
    assert len(payload["scenario_scores"]) == 3
