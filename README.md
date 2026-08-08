# MarketMind AI

MarketMind AI is a preliminary market-screening prototype for coffee shops. It combines nearby-place and Census signals with deterministic, configuration-driven scoring to support structured market comparison. The scores are heuristics for screening and are not empirically validated predictors of business success.

It is **not** a validated predictor of business success, a profitability forecast, an investment recommendation engine, a lease recommendation tool, a complete competitor census, or a general-purpose business-location platform.

## Project status

This repository is a **deployed and tested coffee-shop preliminary market-screening MVP / research prototype**.

The complete scoring, decision, and scenario pipeline is configured and tested for **`coffee_shop`**. Scenarios are coffee-shop-specific. Wider geography and other business types are **future work**, not current product claims.

Verified locally: run **`pytest`** — the full suite must pass. Latest GitHub Actions run on `main` should conclude **success**.

## Quick links

| Link | URL |
|------|-----|
| Live application |(https://marketmind-ai-z47gznxwymayw5nyaegfvu.streamlit.app/) |
| GitHub repository | https://github.com/bchaush/marketmind-ai |
| Current audited commit (scan reports) | [`87b2a15`](https://github.com/bchaush/marketmind-ai/commit/87b2a15ea54d42e427b69b9b82ed8d785253c6e0) |

The live URL above is the public Streamlit URL recorded in `docs/phase7_signoff.md`. Confirm it still matches your Streamlit Community Cloud deployment if you fork or redeploy.

## What the MVP does

1. Enter **latitude**, **longitude**, and **radius (miles)** in the Streamlit sidebar (defaults to the Inman Square vicinity analysis center and 1.0 mile). Business type is fixed to **Coffee shop** (`coffee_shop`) — the only fully supported type.
2. Click **Run Analysis** (subject to a 30-second per-session cooldown and a local daily analysis counter).
3. The app validates the point against a **3.5-mile geofence** centered on the Inman Square vicinity anchor, then retrieves **Google Places Nearby Search** competitor signals and **Census ACS** demographic signals (with circuit-breaker stubs / cascade fallbacks when sources fail).
4. A deterministic, configuration-driven scoring engine produces six 0–100 **decision-support** scores: Demand, Competition Pressure, **Market Gap Proxy**, Risk, Opportunity, and **Data Confidence**. Weights and thresholds are configured heuristics for screening — not empirically validated predictors of real-world business outcomes.
5. Decision rules assign a headline screening status of **GO**, **CAUTION**, or **NO-GO**, plus risks, levers, trade-offs, and threshold-change (“what would change”) conditions.
6. Three coffee-shop **scenarios** are scored as relative viability indices: `study_cafe`, `grab_and_go`, and `third_wave_bar`.
7. An Anthropic-backed analyst report **explains and summarizes** the deterministic payload. It cannot alter official scores, thresholds, status, or scenario calculations, and it does not validate the underlying market model.
8. The UI shows Live vs Cached data badges, **Data Confidence**, and N/A or degraded results when inputs or APIs are incomplete.

## Current supported scope

| Item | Current MVP |
|------|-------------|
| Business type | `coffee_shop` only in the live UI (fully supported and tested). `premium_cafe` exists in taxonomy config only — do not treat it as a completed pipeline. |
| Default location | Inman Square vicinity (`42.3736`, `-71.1097`) — analysis center / geofence anchor, not claimed as the exact neighborhood centroid |
| Geography | Coordinates within **3.5 miles** of that Inman Square vicinity anchor |
| Default radius | **1.0 mile** (sidebar editable; minimum 0.01) |
| Competitor result limit | **Maximum 20** places per Google Places Nearby Search (New) request — not exhaustive competitor coverage |
| Data sources | Google Places Nearby Search; U.S. Census ACS (with documented fallbacks including a Suffolk County baseline) |
| Interface | Streamlit (coordinate inputs — **no address search**) |
| Python | **3.11** (CI + intended Streamlit Cloud setting; `runtime.txt` documents intent) |

## What the outputs mean

| Output | Meaning | Direction |
|--------|---------|-----------|
| **Demand Score** | Configured demographic / local-market **demand proxy** (population and cohort signals) for coffee-shop screening — not measured store demand | Higher is more favorable as a screening signal |
| **Competition Pressure** | Crowding and incumbent strength among **observed** Places matches (up to 20 per analysis — not exhaustive) | Higher is less favorable as a screening signal |
| **Market Gap Proxy** | Configured proxy from demand and inverted competition pressure — **not** a measured unmet-demand census | Higher is more favorable as a screening signal |
| **Risk Score** | Financial / concentration / incumbent risk signal from configured rules | Higher is less favorable as a screening signal |
| **Opportunity Score** | Combined screening headline from demand, gap, and inverted pressure | Higher is more favorable as a screening signal |
| **Data Confidence** | Input/data completeness, source coverage, and geographic fidelity only — **not** predictive certainty or probability of success | Higher means stronger input coverage for screening |
| **Status** | `GO` / `CAUTION` / `NO-GO` from configured decision rules | Screening label only — not investment advice |
| **Scenarios** | Relative viability indices for three coffee-shop concepts | Higher = stronger relative fit — **not** percentages, letter grades, or success probabilities |

Missing metrics can yield **N/A** scores, **DATA_DESERT**-style caution, or other degraded outcomes. Treat every result as **preliminary market screening** that requires independent business validation — not a business plan, profitability forecast, or investment recommendation.

## How the system works

```text
User coordinates and radius
        ↓
Input validation and 3.5-mile Inman Square vicinity geofence
        ↓
Google Places Nearby Search + Census ACS retrieval
  (retries / stubs / cascade fallbacks on failure)
        ↓
Bundle assembly + optional local file cache
        ↓
Deterministic scoring engine (configured weights + thresholds)
        ↓
Decision rules, scenarios, risks, levers, trade-offs, WWC
        ↓
Schema-checked payload → AI explanatory report (does not alter scores)
        ↓
Streamlit display
```

**The LLM does not create, alter, or validate official scores.** Scores and status come from `scoring_engine/` and `decision_engine/` before the report is generated. If the analyst layer is unavailable, deterministic scoring can still remain available.

## Repository guide

| Path | What it contains | When to inspect or change it |
|------|------------------|------------------------------|
| `app.py` | Streamlit UI, cooldown, rate-limit gate, pipeline orchestration, report display, privacy footer | UI copy, session flow, display-only behavior |
| `config/` | Taxonomy, weights, thresholds, decision rules, Boston baseline, CTA, secrets accessors, Census metadata | Any scoring / decision / business-type calibration change |
| `data_layer/` | Google Places and Census clients | API contracts, pagination limits, unit normalization, geocoder cascade |
| `pipeline/` | Live adapter, cache, circuit breaker, rate limiter, telemetry, query builder, bundle assembly | Fetch orchestration, geofence, caching, degradation |
| `scoring_engine/` | Normalizer and six-score engine | Formula or null-handling changes (update tests/docs together) |
| `decision_engine/` | Rules, scenarios, risks, levers, trade-offs, WWC, payload schema | Status logic and scenario weights |
| `report_engine/` | Prompt builder and Anthropic report generation | Explanation wording only — not official scores |
| `ui/` | Payload adapters and developer-view helpers | Display mapping / DEV_MODE payload shape |
| `tests/` | Offline unit and integration tests | Required after behavior changes |
| `docs/` | Phase sign-offs, deployment notes, scoring specification | Audit and operator documentation |
| `audit/` | pip-audit and gitleaks evidence reports | Security / reproducibility evidence |
| `.github/workflows/` | CI pytest on Python 3.11 | CI environment only |

## Important files to change carefully

Changing any of the following usually requires updating **tests**, sometimes **golden snapshots**, and **docs**:

- `scoring_engine/scoring_engine.py`, `scoring_engine/normalizer.py`
- `config/scoring_weights.json`, `config/scoring_thresholds.json`
- `config/decision_logic_rules.json`
- `config/business_taxonomy.json`
- `config/boston_baseline.json`
- Report prompts / schemas under `report_engine/` and `decision_engine/payload_schema.py`
- `requirements.txt` (direct pins) and related CI install steps
- `tests/` expectations

Do not change one in isolation and assume the suite will stay green.

## Run locally

Use **Python 3.11**.

```bash
git clone https://github.com/bchaush/marketmind-ai.git
cd marketmind-ai

# Create venv
python3.11 -m venv .venv
```

Activate:

```powershell
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install and configure:

```bash
pip install -r requirements.txt
pip install pytest   # for local testing
```

Copy `.streamlit/secrets.toml.template` to `.streamlit/secrets.toml` (local only — never commit secrets) and fill in:

- `GOOGLE_PLACES_API_KEY`
- `CENSUS_API_KEY`
- `ANTHROPIC_API_KEY`
- optional: `DEV_MODE`, `CTA_MODE`, `TELEMETRY_ENABLED`

Or set the same names as environment variables / `.env` (also gitignored).

Run the app:

```bash
streamlit run app.py
```

## Testing and audit evidence

Facts verified from this repository at README rewrite time:

| Check | Verified value |
|-------|----------------|
| Local pytest | Full suite must pass (`pytest`) |
| GitHub Actions (`Tests` on `main`) | Latest run **success** ([example](https://github.com/bchaush/marketmind-ai/actions/runs/31066450508) on `a87876b`) |
| Python target | **3.11** (`.github/workflows/tests.yml`, `runtime.txt`; select 3.11 in Streamlit Cloud Advanced settings) |
| Direct dependency pins | `requirements.txt` (exact `==` pins verified on Python 3.11.9) |
| pip-audit | **No known vulnerabilities found** (`audit/pip-audit-report.txt`) |
| gitleaks | **no leaks found** (`audit/gitleaks-report.json`) |
| Commit SHA scanned by those reports | `87b2a15ea54d42e427b69b9b82ed8d785253c6e0` |

`requirements-lock.txt` is an audit freeze artifact of a full 3.11 environment. It is not a substitute for carefully reviewing `requirements.txt`.

## Deployment

The public demo is intended for **Streamlit Community Cloud** with:

- Python **3.11** selected in Cloud Advanced settings (`runtime.txt` documents intent; it is not the sole Cloud version control)
- Secrets stored in Streamlit’s secrets manager (never in git)
- A **30-second** per-session cooldown between runs in `app.py`
- A **local daily analysis limiter** (`pipeline/rate_limiter.py`, default **50**/day on the process filesystem)
- An operator-configured **Google Places ~100 requests/day** quota in GCP (see `docs/DEPLOYMENT.md`)
- Temporary **local file cache** for live bundles (`pipeline/cache.py`, ~14-day TTL under `cache/live_bundles/`)

Local cache and rate-limit files are **not** durable multi-instance production storage. On Streamlit Cloud, treat them as best-effort for a single instance, not a shared database.

## Privacy and external services

Application footer wording (current):

> Location note: the coordinates you enter may be sent to external APIs (Google Places and U.S. Census) to retrieve market signals for this analysis. API responses may be cached temporarily for quota and performance. Stored telemetry (when enabled) rounds coordinates to 3 decimal places and does not store personal identity data.

Also:

- API keys remain server-side (Streamlit secrets / environment) and are not rendered in the public UI
- The project does not intentionally collect personal identity data
- Telemetry is opt-in via `TELEMETRY_ENABLED` and writes rounded coordinates plus outcome fields when enabled

## Limitations / What this project does not claim

- **`coffee_shop` is the only fully supported and tested business type**
- Scenarios are **coffee-shop-specific** (`study_cafe`, `grab_and_go`, `third_wave_bar`)
- Geography is intentionally limited to the **Inman Square vicinity–centered 3.5-mile geofence**
- The public UI accepts **coordinates**, not street addresses
- Google Places Nearby Search (New) returns **at most 20** places per analysis — not an exhaustive competitor census or complete market census
- Competition metrics reflect **observed / returned** matching places from the configured search (taxonomy filters, ranking, and the 20-result cap may omit businesses; indirect competitors may not be captured)
- The competitor-count normalizer is configured on a **0–40** scale for historical / screening range reasons; **live** Nearby Search currently cannot exceed **20** results, so live counts do not span the full configured normalization range
- Places data is filtered by taxonomy rules and remains incomplete relative to the real streetscape
- Census retrieval may use tract / ZCTA / county baseline (placeholder) fallbacks depending on availability, with lower input confidence
- Scoring uses **configured heuristic weights and thresholds** — not empirically validated predictors of real-world business outcomes
- Zero matching Places competitors is an **observational** signal only; it does **not** prove real-world zero competition and does **not** force Opportunity Score to 100
- External API outages can produce **degraded stubs**, missing scores, and lower input confidence
- No profitability prediction or financial forecast
- No lease recommendation, lease-cost model, or rent-roll model
- No financial or investment advice; GO / CAUTION / NO-GO are screening labels only
- No guarantee that a location or coffee-shop format will succeed
- The LLM / Claude layer explains deterministic outputs only; it **does not alter** official scores, thresholds, status, or scenario calculations and does not validate the market model
- Real-world decisions require **independent business validation and due diligence**
- No user accounts
- No persistent production database
- Wider business-type and geography support is future work

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| Missing API keys / auth errors | Streamlit secrets or `.env` / `.streamlit/secrets.toml`; never commit real keys |
| Location outside geofence | Point must be within 3.5 miles of the Inman Square vicinity anchor (`42.3736`, `-71.1097`) |
| Data Desert / many N/A scores | Sparse Census coverage, null metrics, or degraded stubs — confidence will drop |
| Google Places **403** | Key restrictions, billing, or Places API (New) enablement in GCP; logs include status + truncated body only (no key/headers) |
| Daily limit reached | Local limiter (`DAILY_LIMIT` in `pipeline/rate_limiter.py`) or GCP quota |
| Stale results | Sidebar may show Cached data; use **Refresh Data** / clear `cache/live_bundles` (see `scripts/clear_demo_cache.py`) |
| Dependency install failure | Use Python **3.11** and `pip install -r requirements.txt` |

## Final verified summary

MarketMind AI is a preliminary market-screening prototype for coffee shops in a limited Greater Boston geofence. It combines live nearby-place and Census signals with deterministic, configuration-driven scoring and an optional AI explanation layer. Scores are decision-support heuristics for structured comparison — not empirically validated predictors of business success, profitability, or investment outcomes. Real-world decisions require independent validation and due diligence.
