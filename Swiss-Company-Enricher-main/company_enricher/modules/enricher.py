"""High-level enrichment orchestration."""

from __future__ import annotations

from typing import Any

from .scraper import WebsiteScraper
from .search_engine import DuckDuckGoSearcher
from .website_finder import choose_website


class CompanyEnricher:
    def __init__(self, searcher: DuckDuckGoSearcher | None = None, scraper: WebsiteScraper | None = None) -> None:
        self.searcher = searcher or DuckDuckGoSearcher()
        self.scraper = scraper or WebsiteScraper()

    def enrich_row(self, row: dict[str, Any]) -> dict[str, Any]:
        name = str(row.get("Societe") or row.get("Empresa") or "").strip()
        city = str(row.get("Siege") or row.get("Cidade") or "").strip()
        website = str(row.get("Website") or "").strip()

        if not website:
            results = self.searcher.search_company(name, city)
            website = choose_website(results, name, city)

        contact = self.scraper.scrape(website)
        return {
            **row,
            "Website": contact.website or website,
            "Email": "; ".join(contact.emails),
            "Telefone": "; ".join(contact.phones),
            "Codigo_postal": contact.postal_code,
            "Cidade_detectada": contact.city,
            "Facebook": contact.socials.get("facebook", ""),
            "Instagram": contact.socials.get("instagram", ""),
            "LinkedIn": contact.socials.get("linkedin", ""),
            "Paginas_analisadas": "; ".join(contact.pages_scraped),
        }
