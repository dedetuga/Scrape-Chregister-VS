"""Configuration for the Swiss company enrichment pipeline."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_INPUT_CSV = INPUT_DIR / "empresas.csv"
DEFAULT_OUTPUT_CSV = OUTPUT_DIR / "empresas_enriched.csv"
DEFAULT_PROGRESS_DB = OUTPUT_DIR / "progress.db"
DEFAULT_LOG_FILE = OUTPUT_DIR / "logs.txt"

USER_AGENT = (
    "Mozilla/5.0 (compatible; SwissCompanyEnricher/1.0; "
    "+https://example.invalid/bot)"
)
REQUEST_TIMEOUT_SECONDS = 12
DEFAULT_SEARCH_TIMEOUT_SECONDS = 8
MAX_SEARCH_RESULTS = 5
MAX_PAGES_PER_SITE = 6
DEFAULT_WORKERS = 5
DEFAULT_SEARCH_REGION = "ch-fr"
# ddgs "auto" fans out to too many engines at once, which is noisy and quickly
# triggers 429/403 at scale. Instead we give ddgs a short, comma-delimited chain
# of backends: it tries them in order and falls back to the next one whenever a
# backend errors out (rate-limited, blocked, TLS reset, etc.), instead of giving
# up after a single flaky engine. "yahoo" alone was failing constantly with
# connection-reset/TLS errors, so it now sits last, only used if the others fail.
DEFAULT_SEARCH_BACKEND = "yandex, mojeek, startpage"
DEFAULT_SEARCH_DELAY_SECONDS = 2.0
DEFAULT_SEARCH_CONCURRENCY = 1
# How many times to retry the whole backend chain for one company before giving up,
# with exponential backoff. Helps with transient network blips (e.g. the TLS
# "close_notify" resets seen with some backends under load).
DEFAULT_SEARCH_MAX_RETRIES = 3
DEFAULT_SEARCH_RETRY_BASE_SECONDS = 1.5

CONTACT_PATHS = (
    "",
    "contact",
    "contacts",
    "contactez-nous",
    "kontakt",
    "impressum",
    "mentions-legales",
    "mentions-l%C3%A9gales",
    "about",
    "a-propos",
)

SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "x.com": "x",
    "twitter.com": "twitter",
}
