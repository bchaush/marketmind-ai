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
- [ ] Streamlit Cloud runtime is Python 3.11 (`runtime.txt`)

## 4. Python runtime alignment

- CI (GitHub Actions) uses **Python 3.11**
- Production target: **Python 3.11** via root `runtime.txt` (`python-3.11`) for Streamlit Cloud
- Do **not** deploy on floating/latest Python (e.g. 3.14) without re-running the full test suite

## 5. Dependency pinning recommendation

- Keep `requirements.txt` as the human-maintained minimum-version floor for installs
- Keep `requirements-lock.txt` as the audit freeze (`pip freeze`) of a known-good venv
- **Recommendation:** for production/CI reproducibility audits, install from `requirements-lock.txt` **or** pin exact versions into a separate prod lock after review — do **not** blindly overwrite `requirements.txt` with freeze output without reviewing transitive pins
- Privacy note for operators: coordinates may be sent to Google Places / Census; responses may be cached temporarily
