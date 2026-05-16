# MarketMind AI — `config/`

Static configuration shipped with the repo: taxonomy for business types and clustering, plus Boston-area **reference bands** for normalization and UI explanations.

## Files

| File | Purpose |
|------|---------|
| `business_taxonomy.json` | Supported `business_type` keys; hints for external APIs; rules linking `category_tags` to clusters (`premium`, `study_friendly`, `chain`, `budget`). Shared enums align with `query.scenario_config` fields in pipeline snapshots. |
| `boston_baseline_stats.json` | Illustrative numeric bands for dense Boston / campus-adjacent contexts — **not** official statistics. Used later to interpret whether signals are unusually high or low versus this baseline profile. |

## Relationship to mocks

Phase 1 snapshots (and `mock_data/mock_boston_data.json`) should remain consistent with taxonomy labels and cluster names defined here so scoring and UI do not drift.

## Editing conventions

- Bump `schema_version` when structure or semantics change in a breaking way.
- Do **not** store API keys or credentials in this folder — use `.env` or your deployment secret manager.

## Loading

Resolve paths relative to the repository root in development; keep loaders small and explicit so Streamlit and tests share one definition of "where config lives."
