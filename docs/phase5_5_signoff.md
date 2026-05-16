# Phase 5.5 Sign-Off — Infrastructure & Demo Hardening

**Status: Complete**

**Date: 2026-05-15**

**Test Count: 154/154 passing**

---

## What This Phase Was

Phase 5.5 was an infrastructure and demo hardening sprint between the live API integration (Phase 5) and demo readiness (Phase 7). The trigger was a senior review that identified six production risks that would block any public URL share: unstable demo coordinate, developer diagnostics visible to public users, rate-limiting gaps, sequential API fetching, secrets in `.env`, and a misleading cache badge reading the wrong metadata field.

All six were resolved. The engine is now defensively hardened at every layer from the API boundary to the UI.

---

## Blocks Completed

### Block A — Demo Stabilization

- Default coordinate changed from BU (42.3505, -71.1054) to Inman Square (42.3736, -71.1097) — confirmed stable Census block group coverage, existing geofence anchor.
- `DEV_MODE` env var added. `_check_golden_sync()` golden drift warnings only render when `DEV_MODE=true`. Never visible to public users.
- WWC card wording fixed. `_translate_wwc_display()` added to `app.py`. Splits on pipe delimiter, maps each part through `_FLAG_LABELS`. Output is plain English.
- Cache versioning utility added at `scripts/clear_demo_cache.py`. Uses `CACHE_DIR` from `pipeline/cache.py`. Run this after any coordinate or config change to avoid testing against stale bundles.
- Sidebar cache provenance was refined in Block E (`_cache_meta` hit/miss badge, plus `DEV_MODE` cache key caption). Older file-mtime sidebar helpers were superseded.

### Block B — Concurrent Fetching

- Google Places and Census API calls now run in parallel via `ThreadPoolExecutor(max_workers=2)` in `pipeline/live_adapter.py`.
- Circuit breaker behavior preserved per source. Each thread catches its own exceptions and returns the existing failure stub. Google failure never blocks Census path.
- Per-source timeout: `future.result(timeout=20)`. `FuturesTimeoutError` logged distinctly, same stub degradation path as other failures.
- Cache → geofence → concurrent fetch → assemble order unchanged. Bundle schema unchanged. Scoring engine required zero changes.

### Block C — Resilience Layer

- `build_fallback_report()` added to `report_engine/llm_analyst.py`. Builds a full `ReportSchema`-compliant report from deterministic AnalystPayload fields only. No LLM call required. Passes `validate_report()` before returning.
- `generate_report()` returns `tuple[AnalystReport, bool]`. `APITimeoutError` and `InternalServerError` → fallback + `logging.warning`. Exhausted retries → fallback. `RateLimitError` → `LLMQuotaExceededError` (no fallback).
- `LLMQuotaExceededError` custom exception raised on 429. `app.py` catches it separately and shows a calm premium warning. Dashboard scores always render regardless of LLM path.
- `st.info()` banner displayed above analyst report section when fallback was used. Not shown on normal LLM runs.
- 4 new tests in `tests/test_llm_resilience.py`.

### Block D — Security & Deployment

- `config/secrets.py` created as single source of truth for all API key access. `get_secret()` tries `st.secrets` first, falls back to `os.getenv`. Named accessors: `google_api_key()`, `census_api_key()`, `anthropic_api_key()`.
- API key reads consolidated across `data_layer/google_places.py`, `data_layer/census_api.py`, `report_engine/llm_analyst.py`. Other env vars (e.g. `DEV_MODE` in `app.py`) remain `os.getenv` where appropriate.
- `.streamlit/secrets.toml.template` created for deployment reference. Real secrets never committed to git.
- `.gitignore` confirmed: `.env` and `.streamlit/secrets.toml` both excluded.
- `docs/DEPLOYMENT.md` created. Contains step-by-step GCP quota cap instructions, Streamlit Cloud secrets setup, and pre-deploy checklist.
- 30 second per-session cooldown in `app.py`. `last_run_at` set only after successful run. `st.stop()` on violation.
- `pipeline/rate_limiter.py`: global 50 requests/day cap with atomic file writes and midnight reset. Returns `(allowed: bool, remaining: int)`.
- `DEV_MODE` sidebar shows API budget remaining today.
- 4 new tests in `tests/test_rate_limiter.py`.

### Block E — True Cache Hit/Miss Badge

- `pipeline/cache.py` injects `_cache_meta` on cache hit: `cache_hit=True`, `written_at` from file mtime, `key`, `ttl_days`.
- `pipeline/live_adapter.py` injects `_cache_meta` on cache miss: `cache_hit=False`, `written_at=datetime.now()`, same key and `ttl_days`.
- `app.py` sidebar badge reads from `_cache_meta`. Cache hit: `📦 Cached data` plus `Written: {written_at}` (newline in the sidebar message). Cache miss: `🟢 Live data`. `DEV_MODE` additionally shows cache key.
- Old badge logic reading `google_live` from `data_quality` removed. `data_quality` field itself unchanged.
- `_cache_meta` stripped from bundle before `score()` via `clean_bundle` comprehension. Scoring engine never sees it.
- 4 new tests in `tests/test_cache_meta.py`.

---

## Files Created

- `config/secrets.py`
- `pipeline/rate_limiter.py`
- `scripts/clear_demo_cache.py`
- `docs/DEPLOYMENT.md`
- `.streamlit/secrets.toml.template`
- `tests/test_llm_resilience.py`
- `tests/test_rate_limiter.py`
- `tests/test_cache_meta.py`

## Files Modified

- `app.py`
- `pipeline/cache.py`
- `pipeline/live_adapter.py`
- `report_engine/llm_analyst.py`
- `data_layer/google_places.py`
- `data_layer/census_api.py`
- `tests/test_live_cache.py`
- `tests/test_live_adapter.py`

---

## Test Suite Summary

| Suite                        | Tests   | Status        |
|-----------------------------|---------|---------------|
| Phase 1A (Google Places)    | 6       | ✅            |
| Phase 1B (Census API)       | 11      | ✅            |
| Config Integrity            | 1       | ✅            |
| Normalizer                  | 6       | ✅            |
| Scoring Engine              | 33      | ✅            |
| Decision Engine             | 51      | ✅            |
| Live Pipeline (Phase 5)     | 29      | ✅            |
| Golden LLM Prompts          | 5       | ✅            |
| LLM Resilience (new)        | 4       | ✅            |
| Rate Limiter (new)          | 4       | ✅            |
| Cache Metadata (new)        | 4       | ✅            |
| **Total**                   | **154** | **✅ 154/154** |

Run time: ~12s

---

## Architecture Decisions Locked

- `config/secrets.py` is the single source of truth for **API keys**. `get_secret()` uses `st.secrets` → `os.getenv` fallback. That order is permanent for keys.
- `_cache_meta` is a reserved top-level bundle field for runtime UI/decoration. **`set()` persists a disk-only `_cache_meta` record** (e.g. `cache_key`, `created_at`, `source: live_api_cache`) when writing JSON. **`get()` discards that record** and attaches the **badge-shaped** `_cache_meta** (`cache_hit`, `written_at`, `key`, `ttl_days`) for in-memory callers. On cache miss, `live_adapter` attaches the same badge shape before return. **`_cache_meta` is always stripped before `score()`** so the scoring engine never sees either shape.
- Rate limit layers: 30s session cooldown (per user) + 50/day global file counter. GCP hard cap at 100/day is the final backstop.
- Fallback report path: timeout or server error → `build_fallback_report()` → `validate_report()` → `st.info()` banner. 429 → `LLMQuotaExceededError` → premium warning → dashboard still renders.
- Concurrent fetch order: cache check → geofence → `ThreadPoolExecutor` (Google + Census) → assemble. This order is permanent.
- `DEV_MODE` gates: golden sync drift warnings, cache key caption, API budget counter. All three are off by default in production.

---

## Before Production Checklist (Updated)

### Completed across Phases 5, 6, 6-Hardening, 5.5

- [x] Translate raw flag strings to plain language
- [x] Suppress Business Profile raw JSON from UI
- [x] Relabel scenario scores as Relative Viability Index
- [x] Fix sidebar status label post-load
- [x] Payload-aware WWC validation in code
- [x] User-facing confidence language
- [x] Report Quality Gate (flag string scanner)
- [x] 5 golden LLM prompt tests
- [x] Stable demo coordinate (Inman Square)
- [x] `DEV_MODE` gate on diagnostic warnings
- [x] WWC card plain-language rendering
- [x] Cache clear utility script
- [x] Concurrent Google + Census fetching
- [x] Graceful LLM degradation (fallback report)
- [x] LLM quota error premium UI message
- [x] Secrets migration to `config/secrets.py`
- [x] Streamlit `secrets.toml` template
- [x] `docs/DEPLOYMENT.md` with GCP quota steps
- [x] 30s session cooldown rate limiting
- [x] 50/day global rate limiting
- [x] True cache hit/miss badge

### Still required before public URL (Phase 7)

- [ ] GCP hard quota cap set manually in GCP Console
- [ ] Verify stable Census coverage at Inman Square live
- [ ] Boston neighborhood baseline calibration
- [ ] Charles River / zero-data edge case premium message
- [ ] Mobile layout sanity check
- [ ] CTA footer (startup or recruiter version)
- [ ] Developer Mode expander
- [ ] Privacy/data note in footer
- [ ] Silent coordinate telemetry log
- [ ] Evaluation bench (LLM-as-judge)
- [ ] Full pytest run after any future `app.py` change
