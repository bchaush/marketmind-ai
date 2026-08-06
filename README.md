# MarketMind AI

MarketMind AI is a Streamlit web app that screens coffee-shop market opportunities for locations inside a limited Greater Boston geofence. You enter coordinates and a search radius; the app pulls Google Places Nearby Search and U.S. Census signals, runs a deterministic scoring and decision engine, and then generates an explanatory AI report that describes those results. It does not invent official scores, forecast profit, or recommend leases.

## Project status

This repository is a **deployed and tested coffee-shop market-screening MVP**.

The complete scoring, decision, and scenario pipeline is calibrated for **`coffee_shop`**. Wider geography and other business types are **future work**, not current product claims.

Verified locally at the time of this README rewrite: **175 passed** (`pytest`). Latest GitHub Actions run on `main` concluded **success**.

## Quick links

| Link | URL |
|------|-----|
| Live application | https://marketmind-ai-graersee39mjsxx57h7fed.streamlit.app |
| GitHub repository | https://github.com/bchaush/marketmind-ai |
| Current audited commit (scan reports) | [`87b2a15`](https://github.com/bchaush/marketmind-ai/commit/87b2a15ea54d42e427b69b9b82ed8d785253c6e0) |

The live URL above is the public Streamlit URL recorded in `docs/phase7_signoff.md`. Confirm it still matches your Streamlit Community Cloud deployment if you fork or redeploy.

## What the MVP does

1. Enter **latitude**, **longitude**, and **radius (miles)** in the Streamlit sidebar (defaults to Inman Square and 1.0 mile). Business type defaults to `coffee_shop`.
2. Click **Run Analysis** (subject to a 30-second per-session cooldown and a local daily analysis counter).
3. The app validates the point against a **3.5-mile geofence** centered on Inman Square, then retrieves **Google Places Nearby Search** competitor signals and **Census ACS** demographic signals (with circuit-breaker stubs / cascade fallbacks when sources fail).
4. A deterministic scoring engine produces six 0–100 scores: Demand, Competition Pressure, Market Gap, Risk, Opportunity, and Confidence.
5. Decision rules assign a headline status of **GO**, **CAUTION**, or **NO-GO**, plus risks, levers, trade-offs, and threshold-change (“what would change”) conditions.
6. Three coffee-shop **scenarios** are scored as relative viability indices: `study_cafe`, `grab_and_go`, and `third_wave_bar`.
7. An Anthropic-backed analyst report **explains** the deterministic payload. It does not calculate or replace the official scores.
8. The UI shows Live vs Cached data badges, confidence, and N/A or degraded results when inputs or APIs are incomplete.

## Current supported scope

| Item | Current MVP |
|------|-------------|
| Business type | `coffee_shop` (fully supported). `premium_cafe` exists in taxonomy config only — do not treat it as a completed pipeline. |
| Default location | Inman Square (`42.3736`, `-71.1097`) |
| Geography | Coordinates within **3.5 miles** of Inman Square |
| Default radius | **1.0 mile** (sidebar editable; minimum 0.01) |
| Competitor result limit | **Maximum 20** places per Google Places Nearby Search (New) request |
| Data sources | Google Places Nearby Search; U.S. Census ACS (with documented fallbacks including a Suffolk County baseline) |
| Interface | Streamlit (coordinate inputs — **no address search**) |
| Python | **3.11** (CI + intended Streamlit Cloud setting; `runtime.txt` documents intent) |

## What the outputs mean

| Output | Meaning | Direction |
|--------|---------|-----------|
| **Demand Score** | Local population / cohort demand signal for coffee-shop strategy | Higher is more favorable |
| **Competition Pressure** | Crowding and incumbent strength nearby | Higher is less favorable |
| **Market Gap** | Demand relative to competitive pressure | Higher is more favorable |
| **Risk Score** | Financial / concentration / incumbent risk signal | Higher is less favorable |
| **Opportunity Score** | Combined screening headline from demand, gap, and inverted pressure | Higher is more favorable |
| **Confidence Score** | How complete and geographically faithful the inputs appear | Higher is more favorable |
| **Status** | `GO` / `CAUTION` / `NO-GO` from decision rules | Screening label only |
| **Scenarios** | Relative viability indices for three coffee-shop concepts | Higher = stronger relative fit — **not** percentages, letter grades, or success probabilities |

Missing metrics can yield **N/A** scores, **DATA_DESERT**-style caution, or other degraded outcomes. Treat every result as an **initial screen**, not a business plan.

## How the system works

```text
User coordinates and radius
        ↓
Input validation and 3.5-mile Inman Square geofence
        ↓
Google Places Nearby Search + Census ACS retrieval
  (retries / stubs / cascade fallbacks on failure)
        ↓
Bundle assembly + optional local file cache
        ↓
Deterministic scoring engine (weights + thresholds)
        ↓
Decision rules, scenarios, risks, levers, trade-offs, WWC
        ↓
Validated payload → AI explanatory report
        ↓
Streamlit display
```

**The LLM does not create or alter official scores.** Scores and status come from `scoring_engine/` and `decision_engine/` before the report is generated.

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
| Local pytest | **175 passed** |
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

## Known boundaries and limitations

- **`coffee_shop` is the only fully supported business type**
- Geography is limited to the **Inman Square–centered 3.5-mile geofence**
- The public UI accepts **coordinates**, not street addresses
- Google Places Nearby Search (New) returns **at most 20** places per request — not an exhaustive competitor census
- Places data is filtered by taxonomy rules and still incomplete relative to the real streetscape
- Census retrieval may use tract / ZCTA / Suffolk baseline fallbacks with lower confidence
- External API outages can produce **degraded stubs**, missing scores, and lower confidence
- Scenarios are **coffee-shop-specific**
- No user accounts
- No persistent production database
- No profitability prediction
- No lease-cost or rent-roll model
- No financial or investment advice
- Outputs require real-world validation before any business decision

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| Missing API keys / auth errors | Streamlit secrets or `.env` / `.streamlit/secrets.toml`; never commit real keys |
| Location outside geofence | Point must be within 3.5 miles of Inman Square (`42.3736`, `-71.1097`) |
| Data Desert / many N/A scores | Sparse Census coverage, null metrics, or degraded stubs — confidence will drop |
| Google Places **403** | Key restrictions, billing, or Places API (New) enablement in GCP; logs include status + truncated body only (no key/headers) |
| Daily limit reached | Local limiter (`DAILY_LIMIT` in `pipeline/rate_limiter.py`) or GCP quota |
| Stale results | Sidebar may show Cached data; use **Refresh Data** / clear `cache/live_bundles` (see `scripts/clear_demo_cache.py`) |
| Dependency install failure | Use Python **3.11** and `pip install -r requirements.txt` |

## Final verified summary

MarketMind AI is a deployed coffee-shop market-screening MVP for a limited Greater Boston area. It combines live external data, deterministic scoring, decision rules, and a validated explanatory report. It is intended for initial screening and engineering demonstration, not as a substitute for professional market research or investment due diligence.
