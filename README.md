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

## Audit / Reproducibility

- Install dependencies: `pip install -r requirements.txt` (use a venv; optional lock snapshot: `pip freeze > requirements-lock.txt`)
- Run tests: `pytest --tb=short -q` (or `.\venv\Scripts\python.exe -m pytest --tb=short -q`)
- Security scans: `pip-audit -r requirements.txt` and `gitleaks detect --source .` (see `AUDIT_CHECKLIST.md`)
- Secrets must come from Streamlit Cloud secrets or environment variables — never commit `.env` or `.streamlit/secrets.toml`
- Runtime cache, logs, and raw API response dumps under `cache/`, `logs/`, and `data/raw/` are intentionally excluded from Git
- Production/CI target Python **3.11** (`runtime.txt` + GitHub Actions). Prefer aligning installs to `requirements-lock.txt` for audit reproducibility; do not blindly replace `requirements.txt`
- Privacy: entered coordinates may be sent to Google Places and Census; API responses may be cached temporarily
