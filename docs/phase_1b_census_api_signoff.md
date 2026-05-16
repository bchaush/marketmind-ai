# Phase 1B Sign-Off — Census API
**Status: Complete**
**Date: 2026-05-04**

## Tests Passed
- 8/8 offline unit tests green
- Total suite: 14/14 (includes Phase 1A)

## Architecture Decisions Locked
- ACS dataset: acs/acs5, release year 2022
- Geography: block group first (summary level 150)
- FIPS conversion: Census Geocoder API
  (geocoding.geo.census.gov)
- Fallback cascade: BG → Tract → ZCTA → Placeholder
- Confidence penalty: -10 per fallback step
- Output contract: CensusData Pydantic model
- Single source of truth for keys:
  CensusData.model_fields
- No silent zero coercion — suppressed values = None
- Geocoder failure degrades to placeholder,
  does not crash
- census_geocoder.py left as empty placeholder —
  geocoding handled internally in census_api.py
  via geocode_latlng_to_fips()

## Variable Codes Locked (ACS 2022)
- pop_total: B01003_001E
- median_household_income: B19013_001E
- median_age: B01002_001E
- college_student_population_pct:
  B14001_008E + 009E + 017E + 018E / B01003_001E
- age_22_34_count:
  Male B01001_010E+011E+012E +
  Female B01001_034E+035E+036E
- rent_to_income_ratio: B25071_001E

## Known Future Requirement
- Boston neighborhood placeholder values are all
  None. Must be populated with real averages
  before production deployment.
