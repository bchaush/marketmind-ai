from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest
import requests

from data_layer import census_api as ca


def test_fips_conversion_handles_missing_block_group_zip_present():
    geo_json = {
        "result": {
            "addressMatches": [{"addressComponents": {"zip": "02129"}}],
            "geographies": {
                "Census Tracts": [
                    {
                        "STATE": "25",
                        "COUNTY": "025",
                        "TRACT": "010200",
                        "GEOID": "25025010200",
                    }
                ]
            },
        }
    }
    parsed = ca.parse_geocoder_response(geo_json)
    assert parsed["zip"] == "02129"
    assert parsed["state_fips"] == "25"
    assert parsed["county_fips"] == "025"
    assert parsed["tract_fips"] == "010200"
    assert parsed["block_group_fips"] is None


def test_fips_conversion_zip_absent_sets_none_and_does_not_crash():
    geo_json = {"result": {"addressMatches": [{}], "geographies": {"Census Tracts": [{"STATE": "25", "COUNTY": "025", "TRACT": "010200"}]}}}
    parsed = ca.parse_geocoder_response(geo_json)
    assert parsed["zip"] is None


def test_fips_extraction_from_census_blocks_key():
    geo_json = {
        "result": {
            "addressMatches": [],
            "geographies": {
                "2020 Census Blocks": [
                    {
                        "STATE": "25",
                        "COUNTY": "025",
                        "TRACT": "010103",
                        "BLKGRP": "3",
                        "GEOID": "250250101033005",
                    }
                ],
                "Census Tracts": [
                    {
                        "STATE": "25",
                        "COUNTY": "025",
                        "TRACT": "010103",
                        "GEOID": "25025010103",
                    }
                ],
            },
        }
    }

    parsed = ca.parse_geocoder_response(geo_json)
    assert parsed["block_group_fips"] == "3"
    assert parsed["tract_fips"] == "010103"
    assert parsed["state_fips"] == "25"
    assert parsed["county_fips"] == "025"


def test_list_of_lists_parsing_correctness():
    acs_json = [["NAME", "B01003_001E", "B19013_001E"], ["bg1", "-666666666", "50000"]]
    d = ca.acs_list_of_lists_to_dict(acs_json)
    assert d["B01003_001E"] is None
    assert d["B19013_001E"] == 50000.0


def test_coerce_acs_value_no_silent_zero():
    assert ca.coerce_acs_value("") is None
    assert ca.coerce_acs_value(None) is None
    assert ca.coerce_acs_value("-666666666") is None


def test_minimum_viable_demographics_false_when_pop_only():
    metrics = {
        "pop_total": 100,
        "median_household_income": None,
        "median_age": None,
        "age_22_34_count": None,
    }
    assert ca._minimum_viable_demographics(metrics) is False


def test_minimum_viable_demographics_true_with_any_demand_signal():
    for key in ("median_household_income", "median_age", "age_22_34_count"):
        metrics = {
            "pop_total": 100,
            "median_household_income": None,
            "median_age": None,
            "age_22_34_count": None,
        }
        metrics[key] = 1
        assert ca._minimum_viable_demographics(metrics) is True


def test_confidence_score_reduction_per_fallback_step_monotonic():
    metadata = {
        "acs_dataset": "acs/acs5",
        "variables": {
            "block_group": {"acs_table": "N/A", "label": "bg", "composition_note": None},
            "pop_total": {"acs_table": "B01003", "acs_release_year": "2022", "label": "pop", "composition_note": None, "acs_variable": "B01003_001E"},
            "median_household_income": {"acs_table": "B19013", "acs_release_year": "2022", "label": "inc", "composition_note": None, "acs_variable": "B19013_001E"},
            "median_age": {"acs_table": "B01002", "acs_release_year": "2022", "label": "age", "composition_note": None, "acs_variable": "B01002_001E"},
            "college_student_population_pct": {
                "acs_table": "B14001",
                "acs_release_year": "2022",
                "label": "stu",
                "composition_note": "x",
                "acs_variables": {"numerator_terms": ["B14001_008E", "B14001_009E"], "denominator": "B01003_001E"},
            },
            "age_22_34_count": {
                "acs_table": "B01001",
                "acs_release_year": "2022",
                "label": "yp",
                "composition_note": "x",
                "acs_variables": {
                    "male_terms": ["B01001_010E", "B01001_011E", "B01001_012E"],
                    "female_terms": ["B01001_034E", "B01001_035E", "B01001_036E"],
                },
            },
            "rent_to_income_ratio": {"acs_table": "B25071", "acs_release_year": "2022", "label": "rent", "composition_note": None, "acs_variable": "B25071_001E"},
        },
    }

    plan = ca.build_acs_variable_plan(metadata)

    fips = {
        "state_fips": "25",
        "county_fips": "025",
        "tract_fips": "010200",
        "block_group_fips": "3",
        "zip": None,
        "raw": {},
    }

    bg = [["NAME", "B01003_001E"], ["x", "100"]]
    tract_full = [
        [
            "NAME",
            "B01003_001E",
            "B19013_001E",
            "B01002_001E",
            "B25071_001E",
            "B14001_008E",
            "B14001_009E",
            "B01001_010E",
            "B01001_011E",
            "B01001_012E",
            "B01001_034E",
            "B01001_035E",
            "B01001_036E",
        ],
        ["t", "100", "50000", "30", "25", "1", "1", "1", "1", "1", "1", "1", "1", "1"],
    ]

    def fake_get(url, params=None, timeout=None):
        u = str(url)
        for_value = (params or {}).get("for", "")
        if "api.census.gov" in u and "block group" in for_value:
            r = Mock()
            r.raise_for_status = Mock()
            r.json = Mock(return_value=bg)
            return r
        if "api.census.gov" in u and for_value.startswith("tract:"):
            r = Mock()
            r.raise_for_status = Mock()
            r.json = Mock(return_value=tract_full)
            return r
        raise AssertionError(f"unexpected GET {u} {params}")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ca, "geocode_latlng_to_fips", lambda *_a, **_k: fips)
        mp.setattr(ca.requests, "get", fake_get)
        out = ca.run_fallback_cascade(lat=42.0, lng=-71.0, metadata=metadata, plan=plan)

    assert isinstance(out, ca.CensusData)
    assert out.pop_total == 100
    assert out.confidence_score == 90
    assert "block_group_incomplete_or_null_metrics" in out.fallback_used


def test_geocoder_zip_extraction_warning_logged(caplog):
    caplog.set_level(logging.WARNING)
    geo_json = {"result": {"addressMatches": [{}], "geographies": {}}}
    ca.parse_geocoder_response(geo_json)
    assert any("missing ZIP" in r.message for r in caplog.records)


def test_fetch_acs_zcta_skips_when_zip_none():
    out = ca.fetch_acs_zcta(zip_code=None, variable_codes=["B01003_001E"], dataset="acs/acs5", year=2022)
    assert out is None


def test_geocoder_total_failure_degrades_gracefully(monkeypatch):
    metadata = {
        "acs_dataset": "acs/acs5",
        "variables": {
            "block_group": {"acs_table": "N/A", "label": "bg", "composition_note": None},
            "pop_total": {"acs_table": "B01003", "acs_release_year": "2022", "label": "pop", "composition_note": None, "acs_variable": "B01003_001E"},
            "median_household_income": {"acs_table": "B19013", "acs_release_year": "2022", "label": "inc", "composition_note": None, "acs_variable": "B19013_001E"},
            "median_age": {"acs_table": "B01002", "acs_release_year": "2022", "label": "age", "composition_note": None, "acs_variable": "B01002_001E"},
            "college_student_population_pct": {
                "acs_table": "B14001",
                "acs_release_year": "2022",
                "label": "stu",
                "composition_note": "x",
                "acs_variables": {"numerator_terms": ["B14001_008E", "B14001_009E"], "denominator": "B01003_001E"},
            },
            "age_22_34_count": {
                "acs_table": "B01001",
                "acs_release_year": "2022",
                "label": "yp",
                "composition_note": "x",
                "acs_variables": {
                    "male_terms": ["B01001_010E", "B01001_011E", "B01001_012E"],
                    "female_terms": ["B01001_034E", "B01001_035E", "B01001_036E"],
                },
            },
            "rent_to_income_ratio": {"acs_table": "B25071", "acs_release_year": "2022", "label": "rent", "composition_note": None, "acs_variable": "B25071_001E"},
        },
    }

    plan = ca.build_acs_variable_plan(metadata)

    def boom_latlng(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(ca, "geocode_latlng_to_fips", boom_latlng)
    monkeypatch.setattr(ca, "fetch_acs_blockgroup", lambda **_kwargs: {})
    monkeypatch.setattr(ca, "fetch_acs_tract", lambda **_kwargs: {})
    monkeypatch.setattr(ca, "fetch_acs_zcta", lambda **_kwargs: None)

    out = ca.run_fallback_cascade(lat=42.0, lng=-71.0, metadata=metadata, plan=plan)

    assert isinstance(out, ca.CensusData)
    assert "geocoder_api_failure:ConnectionError" in out.fallback_used

    geocoder_penalties = [x for x in out.fallback_used if x.startswith("geocoder_api_failure:")]
    assert geocoder_penalties.count("geocoder_api_failure:ConnectionError") == 1

    assert out.geography_level == "placeholder"
