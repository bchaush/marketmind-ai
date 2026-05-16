## Phase 1 — Data Layer (Complete)

- Google Places API: competitor fetch, strength index, clustering (data_layer/google_places.py)
- Census ACS API: block group → tract → ZCTA → placeholder fallback cascade (data_layer/census_api.py)
- 17 unit tests passing
- Minimum viable demographics gate implemented
- Live tested against Boston University coordinates
- Null-preserving data contract: missing ACS values remain null, never coerced to zero
- Raw API audit trail preserved in raw_variables for debugging and replay

## Phase 2 Ground Rules (before we write a single line)

- All scoring formulas must be null-safe: if a metric is null, either reweight to available signals or apply a neutral baseline — never crash, never fake
- All Phase 2 development runs against mock data only (mock_data/mock_boston_data.json) — live APIs are not called until the full scoring engine is built and unit-tested
- Confidence score is reduced when a metric is null and matters to the score — nulls are not silent
- Phase 2 outputs must be deterministic and explainable — no LLM-generated scores
