from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PayloadMetadata(BaseModel):
    model_config = ConfigDict(strict=False)

    spec_version: str
    phase2_spec_ref: str
    business_type: str
    business_profile: dict[str, Any]


class ExecutiveDecision(BaseModel):
    model_config = ConfigDict(strict=False)

    final_status: Literal["GO", "CAUTION", "NO-GO"]
    status_rule_id: str
    triggered_rule_ids: list[str]
    triggered_tags: list[str]


class TradeOffResult(BaseModel):
    model_config = ConfigDict(strict=False)

    rule_id: str
    priority: int
    output_tags: list[str]


class RiskResult(BaseModel):
    model_config = ConfigDict(strict=False)

    rule_id: str
    priority: int
    output_tags: list[str]


class LeverResult(BaseModel):
    model_config = ConfigDict(strict=False)

    rule_id: str
    priority: int
    impact: str
    output_tags: list[str]


class WWCResult(BaseModel):
    model_config = ConfigDict(strict=False)

    rule_id: str
    priority: int
    to_go_tags: list[str]
    to_no_go_tags: list[str]


class ScenarioResult(BaseModel):
    model_config = ConfigDict(strict=False)

    rule_id: str
    scenario: str
    scenario_score: float
    weights_applied: dict[str, float]


class PayloadEvidence(BaseModel):
    model_config = ConfigDict(strict=False)

    scores: dict[str, Any]
    flags: list[str]


class AnalystPayload(BaseModel):
    model_config = ConfigDict(strict=False)

    metadata: PayloadMetadata
    executive_decision: ExecutiveDecision
    trade_offs: list[TradeOffResult]
    risks: list[RiskResult]
    levers: list[LeverResult]
    what_would_change: list[WWCResult]
    scenario_scores: list[ScenarioResult]
    evidence: PayloadEvidence


def validate_analyst_payload(raw: dict) -> AnalystPayload:
    return AnalystPayload.model_validate(raw)
