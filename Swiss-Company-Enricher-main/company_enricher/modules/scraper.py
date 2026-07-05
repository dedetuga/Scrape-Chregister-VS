"""Website scraper for public company contact details."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import CONTACT_PATHS, MAX_PAGES_PER_SITE, REQUEST_TIMEOUT_SECONDS, USER_AGENT
from .extractors import extract_emails, extract_phones, extract_postal_city, extract_social_links, visible_text

LOGGER = logging.getLogger(__name__)


@dataclass
class ScrapedContact:
    website: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    postal_code: str = ""
    city: str = ""
    socials: dict[str, str] = field(default_factory=dict)
    pages_scraped: list[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


class WebsiteScraper:
    def __init__(self) -> None:
        self._thread_local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            self._thread_local.session = session
        return session

    def scrape(self, website: str) -> ScrapedContact:
        base_url = normalize_url(website)
        contact = ScrapedContact(website=base_url)
        if not base_url:
            return contact

        urls = self._candidate_urls(base_url)
        for url in urls[:MAX_PAGES_PER_SITE]:
            soup = self._fetch_soup(url)
            if soup is None:
                continue
            contact.pages_scraped.append(url)
            text = visible_text(soup)
            contact.emails = sorted(set(contact.emails) | set(extract_emails(text, soup)))
            contact.phones = sorted(set(contact.phones) | set(extract_phones(text, soup)))
            if not contact.postal_code:
                contact.postal_code, contact.city = extract_postal_city(text)
            contact.socials.update({k: v for k, v in extract_social_links(soup, url).items() if k not in contact.socials})

            for href in self._contact_links(soup, base_url):
                if href not in urls and len(urls) < MAX_PAGES_PER_SITE:
                    urls.append(href)
        return contact

    def _candidate_urls(self, base_url: str) -> list[str]:
        return [urljoin(f"{base_url}/", path) for path in CONTACT_PATHS]

    def _fetch_soup(self, url: str) -> BeautifulSoup | None:
        try:
            response = self._session().get(url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
            if not response.ok or "text/html" not in response.headers.get("content-type", ""):
                return None
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as exc:
            LOGGER.debug("Failed to fetch %s: %s", url, exc)
            return None

    def _contact_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        base_host = urlparse(base_url).netloc.lower()
        links: list[str] = []
        keywords = ("contact", "kontakt", "impressum", "mention", "about", "a-propos")
        for anchor in soup.select("a[href]"):
            label = f"{anchor.get_text(' ', strip=True)} {anchor.get('href', '')}".lower()
            if not any(keyword in label for keyword in keywords):
                continue
            href = urljoin(base_url, anchor["href"]).split("#", 1)[0].rstrip("/")
            if urlparse(href).netloc.lower() == base_host and href not in links:
                links.append(href)
        return links
