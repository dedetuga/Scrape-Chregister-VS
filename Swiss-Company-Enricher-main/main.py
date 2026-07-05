"""Command-line entry point for enriching Swiss company CSV files."""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from config import (
    DEFAULT_INPUT_CSV,
    DEFAULT_LOG_FILE,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_PROGRESS_DB,
    DEFAULT_SEARCH_BACKEND,
    DEFAULT_SEARCH_CONCURRENCY,
    DEFAULT_SEARCH_DELAY_SECONDS,
    DEFAULT_SEARCH_TIMEOUT_SECONDS,
    DEFAULT_WORKERS,
    OUTPUT_DIR,
)
from company_enricher.modules.cache import ProgressCache
from company_enricher.modules.enricher import CompanyEnricher
from company_enricher.modules.search_engine import DuckDuckGoSearcher, SearchDisabled

NOISY_LOGGERS = ("ddgs", "httpx", "httpcore", "primp")
SEARCH_DISABLED_BACKENDS = {"", "none", "off", "disabled"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich Valais/Swiss company CSV files with public web contact data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_CSV, help="Input CSV path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV, help="Output CSV path")
    parser.add_argument("--cache", type=Path, default=DEFAULT_PROGRESS_DB, help="SQLite progress cache path")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Number of concurrent companies to process")
    parser.add_argument(
        "--search-backend",
        default=DEFAULT_SEARCH_BACKEND,
        help="ddgs backend to use for discovery (for example: yahoo, google, duckduckgo, brave, auto, or none)",
    )
    parser.add_argument(
        "--search-delay",
        type=float,
        default=DEFAULT_SEARCH_DELAY_SECONDS,
        help="Minimum seconds between search requests across all worker threads",
    )
    parser.add_argument(
        "--search-timeout",
        type=float,
        default=DEFAULT_SEARCH_TIMEOUT_SECONDS,
        help="Timeout in seconds for each search-engine request",
    )
    parser.add_argument(
        "--search-concurrency",
        type=int,
        default=DEFAULT_SEARCH_CONCURRENCY,
        help="Maximum simultaneous ddgs search calls, independent from --workers",
    )
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"), help="Application log level")
    return parser.parse_args()


def setup_logging(level: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(DEFAULT_LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def format_missing_input_message(path: Path) -> str:
    requested_path = str(path)
    resolved_path = path.expanduser().resolve(strict=False)
    return (
        f"Input CSV not found: {requested_path}\n"
        f"Resolved path: {resolved_path}\n"
        f"Current working directory: {Path.cwd()}\n\n"
        "Relative --input paths are resolved from the directory where you run the command, "
        "not necessarily from the directory that contains main.py. Use an absolute path, move the CSV to the expected "
        "location, or run the command from the folder that makes the relative path valid.\n"
        "Example: python main.py --input /full/path/to/valais_completo.csv --output output/empresas_enriched.csv"
    )


def read_csv(path: Path) -> pd.DataFrame:
    expanded_path = path.expanduser()
    if not expanded_path.is_file():
        raise FileNotFoundError(format_missing_input_message(path))
    return pd.read_csv(expanded_path, dtype=str).fillna("")


def cache_key(row: dict[str, str]) -> str:
    return row.get("IDE") or f"{row.get('Societe', '')}|{row.get('Siege', '')}"


def build_enricher(args: argparse.Namespace) -> CompanyEnricher:
    backend = str(args.search_backend).strip().lower()
    searcher = SearchDisabled() if backend in SEARCH_DISABLED_BACKENDS else DuckDuckGoSearcher(
        backend=backend,
        delay_seconds=args.search_delay,
        timeout_seconds=args.search_timeout,
        concurrency=args.search_concurrency,
    )
    return CompanyEnricher(searcher=searcher)


def warn_about_search_pressure(args: argparse.Namespace) -> None:
    backend = str(args.search_backend).strip().lower()
    if args.workers > 20 and backend not in SEARCH_DISABLED_BACKENDS:
        logging.warning(
            "--workers=%s is high for public search engines. Scraping may run in many threads, "
            "but ddgs discovery is limited by --search-concurrency=%s and --search-delay=%s to avoid 403/429/timeouts.",
            args.workers,
            args.search_concurrency,
            args.search_delay,
        )


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    warn_about_search_pressure(args)

    try:
        df = read_csv(args.input)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        sys.exit(2)

    rows = df.to_dict(orient="records")
    cache = ProgressCache(args.cache)
    enricher = build_enricher(args)

    def process(row: dict[str, str]) -> dict[str, str]:
        key = cache_key(row)
        cached = cache.get(key)
        if cached:
            return cached
        enriched = enricher.enrich_row(row)
        # Only cache rows where we actually found something useful. Otherwise a
        # transient search failure gets "frozen" forever and future runs keep
        # skipping it as if it had been tried and genuinely came up empty.
        if enriched.get("Website") or enriched.get("Email") or enriched.get("Telefone"):
            cache.set(key, enriched)
        return enriched

    enriched_rows: list[dict[str, str] | None] = [None] * len(rows)
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {executor.submit(process, row): index for index, row in enumerate(rows)}
            for future in tqdm(as_completed(futures), total=len(futures), desc="A enriquecer empresas"):
                enriched_rows[futures[future]] = future.result()
    finally:
        cache.close()

    pd.DataFrame([row for row in enriched_rows if row is not None]).to_csv(args.output, index=False)
    logging.info("Saved %s enriched rows to %s", len(enriched_rows), args.output)


if __name__ == "__main__":
    main()
