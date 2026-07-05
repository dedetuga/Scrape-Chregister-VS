"""Heuristics to choose the most likely official website from search results."""

from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from urllib.parse import urlparse

from .search_engine import SearchResult

LOGGER = logging.getLogger(__name__)

BLOCKED_HOST_KEYWORDS = {
    "admin.ch",
    "zefix",
    "moneyhouse",
    "local.ch",
    "search.ch",
    "tel.search",
    "yellow.local",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "tripadvisor",
    "booking.com",
    "wikipedia.org",
    "wikidata.org",
    "yandex",
    "startpage.com",
    "mojeek.com",
}

# If the same domain gets chosen as the "best match" for this many DIFFERENT
# companies, it's almost certainly a generic/poisoned result a search engine is
# serving to detected bot traffic (seen in practice: the same unrelated site
# winning for 99% of unrelated companies). At that point we stop trusting it.
MAX_DISTINCT_COMPANIES_PER_DOMAIN = 3

_domain_usage_lock = threading.Lock()
_domain_usage: dict[str, set[str]] = defaultdict(set)


def reset_domain_usage_tracking() -> None:
    """Useful for tests or when starting a fresh run in the same process."""
    with _domain_usage_lock:
        _domain_usage.clear()


def _looks_poisoned(host: str, company_name: str) -> bool:
    with _domain_usage_lock:
        companies = _domain_usage[host]
        if company_name in companies:
            return False
        if len(companies) >= MAX_DISTINCT_COMPANIES_PER_DOMAIN:
            return True
        companies.add(company_name)
        return False


def company_tokens(name: str) -> set[str]:
    cleaned = re.sub(r"\b(sa|sàrl|sarl|gmbh|ag|en liquidation|entreprise individuelle)\b", " ", name.lower())
    return {token for token in re.findall(r"[a-z0-9à-ÿ]{3,}", cleaned) if token not in {"the", "and", "les", "des"}}


def score_result(result: SearchResult, company_name: str, city: str = "") -> int:
    parsed = urlparse(result.url)
    host = parsed.netloc.lower().removeprefix("www.")
    text = f"{result.title} {result.url} {result.snippet}".lower()
    if not parsed.scheme.startswith("http") or any(blocked in host for blocked in BLOCKED_HOST_KEYWORDS):
        return -100

    score = 0
    tokens = company_tokens(company_name)
    score += sum(8 for token in tokens if token in host)
    score += sum(4 for token in tokens if token in text)
    if city and city.lower() in text:
        score += 5
    if host.endswith(".ch"):
        score += 6
    if "contact" in text:
        score += 2
    return score


def choose_website(results: list[SearchResult], company_name: str, city: str = "") -> str:
    scored = sorted(
        ((score_result(row, company_name, city), row.url) for row in results),
        key=lambda pair: pair[0],
        reverse=True,
    )
    for score, url in scored:
        if score <= 0:
            break
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if _looks_poisoned(host, company_name):
            LOGGER.warning(
                "A ignorar '%s' para '%s': já apareceu como 'melhor resultado' para %s empresas "
                "diferentes, é provavelmente um resultado genérico/bloqueado do motor de busca.",
                host,
                company_name,
                MAX_DISTINCT_COMPANIES_PER_DOMAIN,
            )
            continue
        return url
    return ""
