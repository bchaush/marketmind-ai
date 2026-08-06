# MarketMind AI — Deployment Checklist

## 1. GCP Hard Quota Cap (Required before public URL)

Google Places API has no default spend cap. Without this, a single traffic spike can exhaust your monthly free tier in minutes.

Steps:

1. Go to console.cloud.google.com
2. Navigate to APIs & Services → Enabled APIs
3. Click "Places API" (or "Places API (New)")
4. Click "Quotas & System Limits"
5. Find "Requests per day"
6. Click the pencil icon → set limit to 100
7. Click Save
8. Recommended: also set up a billing alert at $10 in Billing → Budgets & Alerts

## 2. Streamlit Cloud Secrets (Required before deploy)

1. Go to share.streamlit.io → your app → Settings → Secrets
2. Paste the contents of .streamlit/secrets.toml.template
3. Fill in real key values
4. Set DEV_MODE = "false" for production
5. Save — the app restarts automatically

## 3. Pre-deploy checklist

- [ ] GCP quota cap set to 100 requests/day
- [ ] Billing alert configured in GCP
- [ ] All secrets in Streamlit Cloud secrets manager
- [ ] .env and secrets.toml confirmed not in git history
- [ ] scripts/clear_demo_cache.py run to clear stale bundles
- [ ] Full pytest run green on the signed-off suite
- [ ] Inman Square coordinate tested live post-deploy
- [ ] Streamlit Community Cloud Advanced settings → Python version set to **3.11** (required; do not rely on `runtime.txt` alone)
- [ ] Root `runtime.txt` documents the intended target (`python-3.11`) for operators/auditors

## 4. Python runtime alignment

- CI (GitHub Actions) uses **Python 3.11**
- Intended production target: **Python 3.11**
- `runtime.txt` records the intended version for documentation/audit, but **Streamlit Community Cloud does not treat `runtime.txt` as the sole controller of the app Python version** — you must **select Python 3.11 in the Streamlit Cloud deployment / Advanced settings** when creating or updating the app
- Do **not** deploy on floating/latest Python (e.g. 3.14) without re-running the full test suite

## 5. Dependency pinning

- `requirements.txt` pins **direct** dependencies to exact versions verified on Python 3.11.9
- `requirements-lock.txt` is an **audit artifact** (`pip freeze` of a known-good 3.11 venv). It is not a blind Windows freeze replacement for `requirements.txt`
- Install for development/CI: `pip install -r requirements.txt` (plus `pytest` for tests)
- Privacy note for operators: coordinates may be sent to Google Places / Census; responses may be cached temporarily
