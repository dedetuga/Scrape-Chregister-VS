"""Helpers that extract public contact data from HTML/text."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import SOCIAL_DOMAINS

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+\s*(?:\[at\]|\(at\)|@)\s*[A-Za-z0-9.-]+\s*(?:\[dot\]|\(dot\)|\.)\s*[A-Za-z]{2,}", re.I)
PHONE_REGEX = re.compile(r"(?:\+41|0041|0)\s?(?:\(0\)\s?)?(?:\d[\s./-]?){8,12}")
POSTAL_CITY_REGEX = re.compile(r"\b(19\d{2}|39\d{2}|18\d{2})\s+([A-ZÀ-Ÿ][A-Za-zÀ-ÿ'’\- ]{2,})")


def visible_text(soup: BeautifulSoup) -> str:
    """Return readable page text without scripts/styles."""
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def normalize_email(value: str) -> str:
    """Normalize common anti-spam email spellings."""
    value = html.unescape(value).strip().lower()
    value = re.sub(r"\s*(?:\[at\]|\(at\)|@)\s*", "@", value, flags=re.I)
    value = re.sub(r"\s*(?:\[dot\]|\(dot\)|\.)\s*", ".", value, flags=re.I)
    return value.strip(".,;:()[]<>")


def extract_emails(text: str, soup: BeautifulSoup | None = None) -> list[str]:
    emails = {normalize_email(match.group(0)) for match in EMAIL_REGEX.finditer(text)}
    if soup is not None:
        for link in soup.select('a[href^="mailto:"]'):
            email = link.get("href", "").split(":", 1)[1].split("?", 1)[0]
            if email:
                emails.add(normalize_email(email))
    return sorted(email for email in emails if "@" in email)


def extract_phones(text: str, soup: BeautifulSoup | None = None) -> list[str]:
    phones = {" ".join(match.group(0).split()) for match in PHONE_REGEX.finditer(text)}
    if soup is not None:
        for link in soup.select('a[href^="tel:"]'):
            phone = link.get("href", "").split(":", 1)[1]
            if phone:
                phones.add(" ".join(phone.split()))
    return sorted(phones)


def extract_postal_city(text: str) -> tuple[str, str]:
    match = POSTAL_CITY_REGEX.search(text)
    if not match:
        return "", ""
    return match.group(1), match.group(2).strip(" ,.-")


def extract_social_links(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor["href"])
        host = urlparse(href).netloc.lower().removeprefix("www.")
        for domain, name in SOCIAL_DOMAINS.items():
            if domain in host and name not in links:
                links[name] = href
    return links


def first_non_empty(values: Iterable[str]) -> str:
    return next((value for value in values if value), "")
