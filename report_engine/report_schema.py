from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

_BANNED_SUBSTRINGS = ("i don't know", "as an ai")


class AnalystReport(BaseModel):
    model_config = ConfigDict(strict=False)

    executive_summary: str
    recommendation: Literal["GO", "CAUTION", "NO-GO"]
    pillar_analysis: str
    scenario_analysis: str
    strategic_levers: list[str]
    hidden_risks: list[str]
    what_would_change: list[str]
    confidence_note: str

    @field_validator("executive_summary")
    @classmethod
    def _validate_executive_summary_length(cls, value: str) -> str:
        length = len(value)
        if length < 50 or length > 400:
            raise ValueError(
                f"executive_summary must be between 50 and 400 characters (got {length})"
            )
        return value

    @field_validator("pillar_analysis")
    @classmethod
    def _validate_pillar_analysis_length(cls, value: str) -> str:
        length = len(value)
        if length < 100 or length > 1000:
            raise ValueError(
                f"pillar_analysis must be between 100 and 1000 characters (got {length})"
            )
        return value

    @field_validator("strategic_levers")
    @classmethod
    def _validate_strategic_levers_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("strategic_levers must contain at least one item")
        return value

    @model_validator(mode="after")
    def _validate_no_banned_substrings(self) -> AnalystReport:
        string_fields: list[tuple[str, str]] = [
            ("executive_summary", self.executive_summary),
            ("pillar_analysis", self.pillar_analysis),
            ("scenario_analysis", self.scenario_analysis),
            ("confidence_note", self.confidence_note),
        ]
        list_fields: list[tuple[str, list[str]]] = [
            ("strategic_levers", self.strategic_levers),
            ("hidden_risks", self.hidden_risks),
            ("what_would_change", self.what_would_change),
        ]

        for field_name, text in string_fields:
            lowered = text.lower()
            for banned in _BANNED_SUBSTRINGS:
                if banned in lowered:
                    raise ValueError(
                        f"{field_name} must not contain the substring {banned!r}"
                    )

        for field_name, items in list_fields:
            for index, item in enumerate(items):
                lowered = item.lower()
                for banned in _BANNED_SUBSTRINGS:
                    if banned in lowered:
                        raise ValueError(
                            f"{field_name}[{index}] must not contain the substring {banned!r}"
                        )

        return self


def validate_report(raw: dict) -> AnalystReport:
    try:
        return AnalystReport.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid analyst report: {exc}") from exc
