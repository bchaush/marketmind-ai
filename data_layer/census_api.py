from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import requests
from config.secrets import census_api_key
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from tenacity import Retrying, RetryError, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class CensusData(BaseModel):
    pop_total: Optional[int] = None
    median_household_income: Optional[float] = None
    median_age: Optional[float] = None
    college_student_population_pct: Optional[float] = None
    age_22_34_count: Optional[int] = None
    rent_to_income_ratio: Optional[float] = None
    geography_level: str
    confidence_score: int
    fallback_used: List[str] = Field(default_factory=list)
    raw_variables: Dict[str, Any] = Field(default_factory=dict)


GEO_CODER_BASE = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

ACS_SUPPRESSION_INT = -666666666


def load_dotenv_if_present() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def get_census_api_key() -> str:
    return census_api_key()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_census_metadata() -> Dict[str, Any]:
    path = _repo_root() / "config" / "census_metadata.json"
    with path.open("r", encoding="utf-8") as f:
        meta = json.load(f)
    if not isinstance(meta, dict):
        raise ValueError("census_metadata.json must be a JSON object")
    vars_ = meta.get("variables")
    if not isinstance(vars_, dict):
        raise ValueError("census_metadata.json missing variables object")
    return meta


def _should_retry_requests(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in (500, 502, 503)
    return False


def _requests_get_with_retries(url: str, *, params: Mapping[str, Any]) -> requests.Response:
    try:
        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=4),
            retry=retry_if_exception(_should_retry_requests),
            reraise=True,
        ):
            with attempt:
                resp = requests.get(url, params=params, timeout=(5, 15))
                resp.raise_for_status()
                return resp
    except RetryError as e:
        logger.exception("HTTP GET failed after retries: %s", url)
        raise e.last_attempt.exception() from e


def _metric_keys() -> List[str]:
    exclude = {
        "geography_level",
        "confidence_score",
        "fallback_used",
        "raw_variables",
    }
    return [k for k in CensusData.model_fields.keys() if k not in exclude]


def _minimum_viable_demographics(metrics: Mapping[str, Any]) -> bool:
    pop_total = metrics.get("pop_total")
    if pop_total is None:
        return False

    demand_signals = [
        metrics.get("median_household_income"),
        metrics.get("median_age"),
        metrics.get("age_22_34_count"),
    ]
    return any(x is not None for x in demand_signals)


def build_acs_variable_plan(metadata: Dict[str, Any]) -> Dict[str, Any]:
    year_raw: Optional[str] = None
    vars_ = metadata.get("variables") or {}
    if not isinstance(vars_, dict):
        raise ValueError("Invalid metadata.variables")

    for _, spec in vars_.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("acs_table") == "N/A":
            continue
        y = spec.get("acs_release_year")
        if isinstance(y, str) and y.strip():
            year_raw = y.strip()
            break
        if isinstance(y, int):
            year_raw = str(y)
            break
    if not year_raw:
        raise ValueError("metadata missing acs_release_year on ACS-backed variables")

    year = int(year_raw)
    dataset = metadata.get("acs_dataset")
    if not isinstance(dataset, str) or not dataset.strip():
        raise ValueError("metadata missing acs_dataset")

    codes: List[str] = []
    computations: List[Dict[str, Any]] = []

    def add_code(c: str) -> None:
        if c not in codes:
            codes.append(c)

    for key, spec in vars_.items():
        if not isinstance(spec, dict):
            continue
        if key == "block_group":
            continue
        if spec.get("acs_table") == "N/A":
            continue

        if "acs_variable" in spec:
            av = spec.get("acs_variable")
            if not isinstance(av, str) or not av.strip():
                raise ValueError(f"{key} has invalid acs_variable")
            add_code(av.strip())

        avs = spec.get("acs_variables")
        if isinstance(avs, dict):
            for v in avs.values():
                if isinstance(v, str) and v.strip():
                    add_code(v.strip())
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and item.strip():
                            add_code(item.strip())

        computations.append({"output_key": key, "spec": spec})

    return {"year": year, "dataset": dataset, "codes": codes, "computations": computations}


def parse_geocoder_response(geocoder_json: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "state_fips": None,
        "county_fips": None,
        "tract_fips": None,
        "block_group_fips": None,
        "zip": None,
        "raw": geocoder_json,
    }

    matches = ((geocoder_json or {}).get("result") or {}).get("addressMatches") or []
    if isinstance(matches, list) and matches and isinstance(matches[0], dict):
        m0 = matches[0]
        comps = m0.get("addressComponents")
        if isinstance(comps, dict):
            z = comps.get("zip")
            if isinstance(z, str) and z.strip():
                out["zip"] = z.strip()
            elif z is None:
                out["zip"] = None
            else:
                out["zip"] = str(z).strip() or None
        if out["zip"] is None:
            logger.warning("Geocoder match missing ZIP; ZCTA fallback will be skipped.")

    geos = ((geocoder_json or {}).get("result") or {}).get("geographies") or {}
    if not isinstance(geos, dict):
        return out

    priority_keys = [
        "2020 Census Blocks",
        "Census Blocks",
        "2020 Census Block Groups",
        "Census Block Groups",
        "2010 Census Block Groups",
        "2020 Census Tracts",
        "Census Tracts",
        "2010 Census Tracts",
    ]

    picked_bg: Optional[Dict[str, Any]] = None
    picked_tract: Optional[Dict[str, Any]] = None
    for k in priority_keys:
        arr = geos.get(k)
        if isinstance(arr, list) and arr and isinstance(arr[0], dict):
            if "Block" in k and picked_bg is None:
                picked_bg = arr[0]
            if "Tract" in k and picked_tract is None:
                picked_tract = arr[0]

    def _digits(s: Any) -> Optional[str]:
        if s is None:
            return None
        if isinstance(s, int):
            return str(s)
        if isinstance(s, str) and s.strip():
            return s.strip()
        return None

    if isinstance(picked_bg, dict):
        out["state_fips"] = _digits(picked_bg.get("STATE")) or out["state_fips"]
        out["county_fips"] = _digits(picked_bg.get("COUNTY")) or out["county_fips"]
        out["tract_fips"] = _digits(picked_bg.get("TRACT")) or out["tract_fips"]
        out["block_group_fips"] = _digits(picked_bg.get("BLKGRP")) or _digits(picked_bg.get("BLOCK_GROUP"))

        geoid = picked_bg.get("GEOID") or picked_bg.get("GEOID10")
        geoid_s = _digits(geoid)
        if geoid_s:
            if out["state_fips"] is None:
                out["state_fips"] = geoid_s[0:2]
            if out["county_fips"] is None:
                out["county_fips"] = geoid_s[2:5]
            if out["tract_fips"] is None:
                out["tract_fips"] = geoid_s[5:11]
            if out["block_group_fips"] is None and len(geoid_s) >= 12:
                out["block_group_fips"] = geoid_s[11:12]

    if out["tract_fips"] is None and isinstance(picked_tract, dict):
        out["state_fips"] = _digits(picked_tract.get("STATE")) or out["state_fips"]
        out["county_fips"] = _digits(picked_tract.get("COUNTY")) or out["county_fips"]
        out["tract_fips"] = _digits(picked_tract.get("TRACT")) or out["tract_fips"]

    return out


def validate_fips_components(fips: Mapping[str, Any]) -> Tuple[bool, str]:
    if fips.get("state_fips") and fips.get("county_fips") and fips.get("tract_fips") and fips.get("block_group_fips"):
        return True, "block_group"
    if fips.get("state_fips") and fips.get("county_fips") and fips.get("tract_fips"):
        return True, "tract"
    return False, "insufficient_fips"


def geocode_latlng_to_fips(lat: float, lng: float) -> Dict[str, Any]:
    params = {
        "x": lng,
        "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    resp = _requests_get_with_retries(GEO_CODER_BASE, params=params)
    payload = resp.json()
    if not isinstance(payload, dict):
        raise ValueError("Geocoder returned non-object JSON")
    parsed = parse_geocoder_response(payload)
    return parsed


def acs_list_of_lists_to_dict(acs_json: Any) -> Dict[str, Optional[float]]:
    if not isinstance(acs_json, list) or len(acs_json) < 2:
        return {}
    header = acs_json[0]
    row = acs_json[1]
    if not isinstance(header, list) or not isinstance(row, list):
        return {}
    out: Dict[str, Optional[float]] = {}
    for i, col in enumerate(header):
        if not isinstance(col, str):
            continue
        if i >= len(row):
            out[col] = None
            continue
        out[col] = coerce_acs_value(row[i])
    return out


def coerce_acs_value(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if s == "":
            return None
        try:
            iv = int(s)
            if iv == ACS_SUPPRESSION_INT:
                return None
            return float(iv)
        except Exception:
            return None
    if isinstance(raw, (int, float)):
        if isinstance(raw, float) and math.isnan(raw):
            return None
        iv = int(raw)
        if iv == ACS_SUPPRESSION_INT:
            return None
        return float(raw)
    return None


def _acs_url(dataset: str, year: int) -> str:
    return f"https://api.census.gov/data/{year}/{dataset}"


def fetch_acs_blockgroup(
    *,
    state_fips: str,
    county_fips: str,
    tract_fips: str,
    block_group_fips: str,
    variable_codes: Sequence[str],
    dataset: str,
    year: int,
) -> Dict[str, Optional[float]]:
    key = get_census_api_key()
    params: Dict[str, Any] = {
        "get": ",".join(["NAME", *variable_codes]),
        "for": f"block group:{block_group_fips}",
        "in": f"state:{state_fips} county:{county_fips} tract:{tract_fips}",
    }
    if key:
        params["key"] = key
    resp = _requests_get_with_retries(_acs_url(dataset, year), params=params)
    return acs_list_of_lists_to_dict(resp.json())


def fetch_acs_tract(
    *,
    state_fips: str,
    county_fips: str,
    tract_fips: str,
    variable_codes: Sequence[str],
    dataset: str,
    year: int,
) -> Dict[str, Optional[float]]:
    key = get_census_api_key()
    params: Dict[str, Any] = {
        "get": ",".join(["NAME", *variable_codes]),
        "for": f"tract:{tract_fips}",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    if key:
        params["key"] = key
    resp = _requests_get_with_retries(_acs_url(dataset, year), params=params)
    return acs_list_of_lists_to_dict(resp.json())


def fetch_acs_zcta(
    *,
    zip_code: Optional[str],
    variable_codes: Sequence[str],
    dataset: str,
    year: int,
) -> Optional[Dict[str, Optional[float]]]:
    if zip_code is None:
        logger.warning("ZIP/ZCTA ACS skipped: missing ZIP from geocoder.")
        return None
    key = get_census_api_key()
    params: Dict[str, Any] = {
        "get": ",".join(["NAME", *variable_codes]),
        "for": f"zip code tabulation area:{zip_code}",
    }
    if key:
        params["key"] = key
    resp = _requests_get_with_retries(_acs_url(dataset, year), params=params)
    return acs_list_of_lists_to_dict(resp.json())


def load_boston_baseline_config() -> Dict[str, Any]:
    """Suffolk County ACS 5-Year anchor values for final cascade fallback only."""
    path = _repo_root() / "config" / "boston_baseline.json"
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("boston_baseline.json must be a JSON object")
    return data


def _baseline_metrics_dict(baseline: Mapping[str, Any]) -> Dict[str, Any]:
    """Map baseline JSON metric keys to CensusData field types."""
    metrics: Dict[str, Any] = {}
    int_keys = {"pop_total", "age_22_34_count"}
    for key in _metric_keys():
        if key not in baseline:
            metrics[key] = None
            continue
        raw = baseline[key]
        if raw is None:
            metrics[key] = None
            continue
        if key in int_keys:
            metrics[key] = int(raw)
            continue
        metrics[key] = float(raw)
    return metrics


def compute_derived_fields(values_by_code: Dict[str, Optional[float]], metadata: Dict[str, Any]) -> Dict[str, Optional[Any]]:
    vars_ = metadata.get("variables") or {}
    if not isinstance(vars_, dict):
        raise ValueError("Invalid metadata.variables")

    out: Dict[str, Optional[Any]] = {}

    def get_code(v: str) -> Optional[float]:
        return values_by_code.get(v)

    def sum_codes(codes: Sequence[str]) -> Optional[float]:
        total = 0.0
        for c in codes:
            val = get_code(c)
            if val is None:
                return None
            total += float(val)
        return total

    for output_key, spec in vars_.items():
        if not isinstance(spec, dict):
            continue
        if output_key == "block_group":
            continue
        if spec.get("acs_table") == "N/A":
            continue

        if output_key == "pop_total":
            av = spec.get("acs_variable")
            if isinstance(av, str):
                v = get_code(av)
                out[output_key] = int(v) if v is not None else None
            continue

        if output_key in {"median_household_income", "median_age", "rent_to_income_ratio"}:
            av = spec.get("acs_variable")
            if isinstance(av, str):
                out[output_key] = get_code(av)
            continue

        if output_key == "college_student_population_pct":
            avs = spec.get("acs_variables") or {}
            if not isinstance(avs, dict):
                out[output_key] = None
                continue
            nums = avs.get("numerator_terms") or []
            den = avs.get("denominator")
            if not isinstance(nums, list) or not isinstance(den, str):
                out[output_key] = None
                continue
            num_sum = sum_codes([x for x in nums if isinstance(x, str)])
            den_v = get_code(den)
            if num_sum is None or den_v is None or den_v == 0:
                out[output_key] = None
            else:
                out[output_key] = float(num_sum) / float(den_v)
            continue

        if output_key == "age_22_34_count":
            avs = spec.get("acs_variables") or {}
            if not isinstance(avs, dict):
                out[output_key] = None
                continue
            male = avs.get("male_terms") or []
            female = avs.get("female_terms") or []
            if not isinstance(male, list) or not isinstance(female, list):
                out[output_key] = None
                continue
            m_sum = sum_codes([x for x in male if isinstance(x, str)])
            f_sum = sum_codes([x for x in female if isinstance(x, str)])
            if m_sum is None or f_sum is None:
                out[output_key] = None
            else:
                out[output_key] = int(m_sum + f_sum)
            continue

    return out


def assemble_output_dict(
    *,
    metrics: Dict[str, Any],
    geography_level: str,
    confidence_score: int,
    fallback_used: List[str],
    raw_variables: Dict[str, Any],
) -> CensusData:
    try:
        return CensusData(
            **{k: metrics.get(k) for k in _metric_keys()},
            geography_level=geography_level,
            confidence_score=confidence_score,
            fallback_used=fallback_used,
            raw_variables=raw_variables,
        )
    except ValidationError as e:
        logger.exception("CensusData validation failed")
        raise


def run_fallback_cascade(
    *,
    lat: float,
    lng: float,
    metadata: Dict[str, Any],
    plan: Dict[str, Any],
) -> CensusData:
    year = int(plan["year"])
    dataset = str(plan["dataset"])
    codes = plan["codes"]

    fallback_used: List[str] = []
    raw_bundle: Dict[str, Any] = {"geocoder": None, "acs_attempts": []}
    confidence_score = 100
    current_geography = "unknown"

    def penalize(reason: str) -> None:
        nonlocal confidence_score
        fallback_used.append(reason)
        confidence_score -= 10

    try:
        fips = geocode_latlng_to_fips(lat, lng)
        raw_bundle["geocoder"] = fips.get("raw")
        ok, level_hint = validate_fips_components(fips)
        if not ok:
            penalize("geocoder_insufficient_fips")
    except Exception as e:
        logger.error("Geocoder API completely failed: %s", e)
        fips = {}
        ok, level_hint = False, "insufficient_fips"
        penalize(f"geocoder_api_failure:{type(e).__name__}")

    def attempt(label: str, values_by_code: Dict[str, Optional[float]]) -> Dict[str, Any]:
        metrics = compute_derived_fields(values_by_code, metadata)
        raw_bundle["acs_attempts"].append({"label": label, "values_by_code": values_by_code, "metrics": dict(metrics)})
        return metrics

    metrics: Optional[Dict[str, Any]] = None

    # 1) Block group
    if ok and level_hint == "block_group":
        try:
            vals = fetch_acs_blockgroup(
                state_fips=str(fips["state_fips"]),
                county_fips=str(fips["county_fips"]),
                tract_fips=str(fips["tract_fips"]),
                block_group_fips=str(fips["block_group_fips"]),
                variable_codes=codes,
                dataset=dataset,
                year=year,
            )
            metrics = attempt("block_group", vals)
            if _minimum_viable_demographics(metrics):
                current_geography = "block_group"
                confidence_score = max(0, int(confidence_score))
                return assemble_output_dict(
                    metrics=metrics,
                    geography_level=current_geography,
                    confidence_score=confidence_score,
                    fallback_used=fallback_used,
                    raw_variables=raw_bundle,
                )
            penalize("block_group_incomplete_or_null_metrics")
        except Exception as e:
            penalize(f"block_group_fetch_failed:{type(e).__name__}")
    elif ok and level_hint == "tract":
        penalize("geocoder_missing_block_group")
    else:
        penalize("cannot_start_at_block_group")

    # 2) Tract
    if metrics is None or not _minimum_viable_demographics(metrics):
        if fips.get("state_fips") and fips.get("county_fips") and fips.get("tract_fips"):
            try:
                vals = fetch_acs_tract(
                    state_fips=str(fips["state_fips"]),
                    county_fips=str(fips["county_fips"]),
                    tract_fips=str(fips["tract_fips"]),
                    variable_codes=codes,
                    dataset=dataset,
                    year=year,
                )
                metrics = attempt("tract", vals)
                if _minimum_viable_demographics(metrics):
                    current_geography = "tract"
                    confidence_score = max(0, int(confidence_score))
                    return assemble_output_dict(
                        metrics=metrics,
                        geography_level=current_geography,
                        confidence_score=confidence_score,
                        fallback_used=fallback_used,
                        raw_variables=raw_bundle,
                    )
                penalize("tract_incomplete_or_null_metrics")
            except Exception as e:
                penalize(f"tract_fetch_failed:{type(e).__name__}")
        else:
            penalize("tract_unavailable_missing_tract_fips")

    # 3) ZCTA (requires ZIP); skip API entirely if missing
    if metrics is None or not _minimum_viable_demographics(metrics):
        zip_code = fips.get("zip")
        zvals = fetch_acs_zcta(zip_code=zip_code, variable_codes=codes, dataset=dataset, year=year)
        if zvals is None:
            penalize("zcta_skipped_missing_zip")
        else:
            try:
                metrics = attempt("zcta", zvals)
                if _minimum_viable_demographics(metrics):
                    current_geography = "zcta"
                    confidence_score = max(0, int(confidence_score))
                    return assemble_output_dict(
                        metrics=metrics,
                        geography_level=current_geography,
                        confidence_score=confidence_score,
                        fallback_used=fallback_used,
                        raw_variables=raw_bundle,
                    )
                penalize("zcta_incomplete_or_null_metrics")
            except Exception as e:
                penalize(f"zcta_fetch_failed:{type(e).__name__}")

    # 4) Suffolk baseline (final cascade step — seeded ACS county estimates, not block-group truth)
    if metrics is None or not _minimum_viable_demographics(metrics):
        penalize("boston_baseline")
        raw_baseline = load_boston_baseline_config()
        metrics = _baseline_metrics_dict(raw_baseline)
        raw_bundle["acs_attempts"].append(
            {
                "label": "boston_baseline",
                "values_by_code": {},
                "metrics": dict(metrics),
            }
        )
        logger.info(
            "Census cascade using boston_baseline final fallback (%s)",
            raw_baseline.get("_source"),
        )
        current_geography = "placeholder"

    confidence_score = max(0, int(confidence_score))

    return assemble_output_dict(
        metrics=metrics or {k: None for k in _metric_keys()},
        geography_level=current_geography,
        confidence_score=confidence_score,
        fallback_used=fallback_used,
        raw_variables=raw_bundle,
    )


def fetch_census_demographics(query: Dict[str, Any]) -> CensusData:
    load_dotenv_if_present()
    metadata = load_census_metadata()
    plan = build_acs_variable_plan(metadata)
    lat = float(query["lat"])
    lng = float(query["lng"])
    return run_fallback_cascade(lat=lat, lng=lng, metadata=metadata, plan=plan)
