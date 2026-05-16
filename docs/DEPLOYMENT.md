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
- [ ] Full pytest run: 150/150 passing
- [ ] Inman Square coordinate tested live post-deploy
