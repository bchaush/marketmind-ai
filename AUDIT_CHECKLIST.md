# MarketMind AI — Audit Checklist

Use this checklist for a professional reproducibility and security audit.
It does **not** change product behavior. Secrets must never be printed or committed.

---

## 1. Run the test suite

From the repo root (Windows PowerShell, with the project venv):

```powershell
cd C:\Users\Bora\Desktop\marketmind-ai
.\venv\Scripts\python.exe -m pytest --tb=short -q
```

Or with pytest on PATH after activating the venv:

```powershell
.\venv\Scripts\Activate.ps1
pytest -v
```

Expected: **169 passed** (current signed-off suite size).

---

## 2. Generate a dependency lockfile

Do **not** replace `requirements.txt` unless explicitly approved.
Generate a freeze snapshot for audit reproducibility:

```powershell
.\venv\Scripts\python.exe -m pip freeze > requirements-lock.txt
```

Review `requirements-lock.txt` before committing. It pins exact installed versions from the current environment.

**Pinning recommendation:** keep `requirements.txt` as the install floor; use `requirements-lock.txt` for reproducible audit/CI installs. Align production with **Python 3.11** (`runtime.txt` + GitHub Actions). Do not blindly overwrite `requirements.txt` with freeze output.

---

## 3. Run pip-audit (dependency vulnerability scan)

If `pip-audit` is installed in the venv:

```powershell
mkdir audit -Force
.\venv\Scripts\python.exe -m pip_audit -r requirements.txt -f text > audit\pip-audit-report.txt
```

If not installed, install **only if you approve**, then re-run:

```powershell
.\venv\Scripts\python.exe -m pip install pip-audit
.\venv\Scripts\python.exe -m pip_audit -r requirements.txt -f text > audit\pip-audit-report.txt
```

Optional (scan the locked freeze):

```powershell
.\venv\Scripts\python.exe -m pip_audit -r requirements-lock.txt -f text > audit\pip-audit-report.txt
```

---

## 4. Run gitleaks (secret scan)

If `gitleaks` is on PATH:

```powershell
mkdir audit -Force
gitleaks detect --source . --report-path audit\gitleaks-report.json --report-format json
```

If not installed, install via an approved method (e.g. GitHub releases / package manager), then re-run the command above.
Do not paste secret values into chat if any findings appear — rotate credentials instead.

---

## 5. Check git status

```powershell
git status
git status --ignored
```

Confirm:

- `.env` is ignored and untracked
- `.streamlit/secrets.toml` is ignored and untracked (if present locally)
- `cache/` runtime files are ignored
- `logs/` and `*.jsonl` are ignored
- `data/raw/` response dumps are ignored (keep `data/raw/.gitkeep` only)
- `venv/` is ignored

---

## 6. Confirm secrets are not committed

```powershell
git check-ignore -v .env
git check-ignore -v .streamlit/secrets.toml
git log --all -- .env
git log --all -- .streamlit/secrets.toml
git ls-files | Select-String -Pattern "\.env$|secrets\.toml$|rate_limit_counter|telemetry\.jsonl"
```

Rules:

- `git check-ignore -v` must show `.gitignore` matching `.env` and `secrets.toml`
- `git log --all -- .env` and `... secrets.toml` should print **nothing**
- `git ls-files` must **not** list `.env`, real `secrets.toml`, or telemetry JSONL

Template only (safe): `.streamlit/secrets.toml.template`

---

## 7. Manual evidence still needed (screenshots / console captures)

### Streamlit Cloud

Capture:

1. App settings → **Secrets** page (blur values; show that keys exist, not the values)
2. Successful live run: Live/Cached badge, scores, confidence, status
3. CTA footer rendering (headline + GitHub link; no broken placeholders)
4. Mobile viewport (≈390px): three tabs visible
5. Confirmation `DEV_MODE` is off in production secrets
6. Confirmation `TELEMETRY_ENABLED` setting as deployed

### Google Cloud / GCP

Capture:

1. Places API (or Maps Platform) **quota / daily cap** (e.g. 100 requests/day)
2. Billing **budget / alert** threshold (e.g. $10)
3. API key restrictions summary (application + API restrictions) — blur the key itself

### GitHub

Capture:

1. Repo visibility (Private)
2. Actions run for `.github/workflows/tests.yml` (green check)
3. Branch protection / PR checks if enabled (optional but recommended)

---

## 8. What is intentionally excluded from Git

| Path / pattern | Why |
|----------------|-----|
| `.env`, `.env.*` | Local API keys |
| `.streamlit/secrets.toml` | Local Streamlit secrets |
| `cache/**` | Live bundle cache + rate-limit counter |
| `logs/`, `*.jsonl` | Telemetry / append-only logs |
| `data/raw/**` | Raw/processed API dumps |
| `venv/`, `.venv/` | Virtualenv |
| `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Tool caches |
| `build/`, `dist/`, `*.log` | Build / log noise |

Kept for clone structure: `cache/live_bundles/.gitkeep`, `data/raw/.gitkeep`.
Kept for demos/tests: `mock_data/`, config JSON, docs, tests, templates.
