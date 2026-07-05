"""Search integration used to discover likely official websites."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from ddgs import DDGS

from config import (
    DEFAULT_SEARCH_BACKEND,
    DEFAULT_SEARCH_CONCURRENCY,
    DEFAULT_SEARCH_DELAY_SECONDS,
    DEFAULT_SEARCH_MAX_RETRIES,
    DEFAULT_SEARCH_REGION,
    DEFAULT_SEARCH_RETRY_BASE_SECONDS,
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    MAX_SEARCH_RESULTS,
)

LOGGER = logging.getLogger(__name__)
_SEARCH_LOCK = threading.Lock()
_NEXT_SEARCH_AT = 0.0


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class SearchDisabled:
    """Searcher implementation for runs that should only scrape existing Website values."""

    def search_company(self, name: str, city: str = "", canton: str = "Valais") -> list[SearchResult]:
        return []


class DuckDuckGoSearcher:
    """Small wrapper around ddgs with conservative rate limiting.

    The ddgs ``auto`` backend fans out to many public engines. That is fragile for
    30k+ row files because every company can trigger requests to Google, Brave,
    Wikipedia, Mojeek, etc. This wrapper defaults to one backend and protects
    calls with a small concurrency limit plus a global inter-request delay.
    """

    def __init__(
        self,
        region: str = DEFAULT_SEARCH_REGION,
        max_results: int = MAX_SEARCH_RESULTS,
        backend: str = DEFAULT_SEARCH_BACKEND,
        delay_seconds: float = DEFAULT_SEARCH_DELAY_SECONDS,
        timeout_seconds: float = DEFAULT_SEARCH_TIMEOUT_SECONDS,
        concurrency: int = DEFAULT_SEARCH_CONCURRENCY,
        max_retries: int = DEFAULT_SEARCH_MAX_RETRIES,
        retry_base_seconds: float = DEFAULT_SEARCH_RETRY_BASE_SECONDS,
    ) -> None:
        self.region = region
        self.max_results = max(1, max_results)
        # Keep the individual backend names so we can rotate their order per call,
        # instead of always hammering the same "first" backend for every company.
        self._backend_pool = [b.strip() for b in self._normalize_backend(backend).split(",") if b.strip()]
        self._rotation_index = 0
        self.delay_seconds = max(0.0, delay_seconds)
        self.timeout_seconds = max(1.0, timeout_seconds)
        self._semaphore = threading.BoundedSemaphore(max(1, concurrency))
        self.max_retries = max(1, max_retries)
        self.retry_base_seconds = max(0.1, retry_base_seconds)

    def _next_backend_chain(self) -> str:
        """Rotate which backend goes first, so load is spread evenly across all of them."""
        if not self._backend_pool:
            return DEFAULT_SEARCH_BACKEND
        with _SEARCH_LOCK:
            start = self._rotation_index % len(self._backend_pool)
            self._rotation_index += 1
        rotated = self._backend_pool[start:] + self._backend_pool[:start]
        return ", ".join(rotated)

    def search_company(self, name: str, city: str = "", canton: str = "Valais") -> list[SearchResult]:
        query = " ".join(part for part in [f'"{name}"', city, canton, "Suisse contact"] if part)
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            backend_chain = self._next_backend_chain()
            with self._semaphore:
                self._wait_for_rate_limit()
                try:
                    with DDGS(timeout=self.timeout_seconds) as ddgs:
                        rows = ddgs.text(
                            query,
                            region=self.region,
                            max_results=self.max_results,
                            backend=backend_chain,
                        )
                        return [
                            SearchResult(
                                title=row.get("title", ""),
                                url=row.get("href") or row.get("url", ""),
                                snippet=row.get("body", ""),
                            )
                            for row in rows
                            if row.get("href") or row.get("url")
                        ]
                except Exception as exc:  # Search providers are network-dependent and can block/timeout.
                    last_error = exc
                    LOGGER.warning(
                        "Search attempt %s/%s failed for %s with backend=%s: %s",
                        attempt + 1,
                        self.max_retries,
                        name,
                        backend_chain,
                        exc,
                    )
            if attempt + 1 < self.max_retries:
                time.sleep(self.retry_base_seconds * (2 ** attempt))
        LOGGER.error("Search permanently failed for %s after %s attempts: %s", name, self.max_retries, last_error)
        return []

    @staticmethod
    def _normalize_backend(backend: str) -> str:
        backend = (backend or DEFAULT_SEARCH_BACKEND).strip().lower()
        if backend == "auto":
            LOGGER.warning("ddgs backend 'auto' is too noisy at scale; using '%s' instead", DEFAULT_SEARCH_BACKEND)
            return DEFAULT_SEARCH_BACKEND
        return backend

    def _wait_for_rate_limit(self) -> None:
        """Throttle all search calls across worker threads to reduce 403/429 responses."""
        global _NEXT_SEARCH_AT
        if self.delay_seconds <= 0:
            return
        with _SEARCH_LOCK:
            now = time.monotonic()
            if now < _NEXT_SEARCH_AT:
                time.sleep(_NEXT_SEARCH_AT - now)
                now = time.monotonic()
            _NEXT_SEARCH_AT = now + self.delay_seconds
