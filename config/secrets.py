"""Single source of truth for API keys (Streamlit secrets + local .env fallback)."""

from __future__ import annotations

import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)


def get_secret(key: str) -> str:
    """
    Retrieve a secret by key.
    Priority order:
      1. st.secrets (Streamlit Cloud / secrets.toml)
      2. os.getenv (local .env via load_dotenv)
    Returns empty string if not found — never crashes.
    Logs a warning if the key is missing from both sources.
    """
    try:
        value = st.secrets.get(key, None)
        if value:
            return str(value)
    except Exception:
        pass  # st.secrets not available (CLI scripts, tests)
    value = os.getenv(key, "")
    if not value:
        logger.warning("Secret '%s' not found in st.secrets or environment.", key)
    return value


def google_api_key() -> str:
    primary = get_secret("GOOGLE_PLACES_API_KEY")
    if primary:
        return primary
    return get_secret("GOOGLE_API_KEY")


def census_api_key() -> str:
    return get_secret("CENSUS_API_KEY")


def anthropic_api_key() -> str:
    return get_secret("ANTHROPIC_API_KEY")
