"""
Visits a company's own public website (homepage + likely contact/about
pages only — never LinkedIn, job boards, or anything behind a login) and
extracts emails, phone numbers, and a company name guess.
"""

import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LeadResearchBot/1.0; "
                   "+https://example.com/bot-info)"
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.\-]?)?(\(?\d{2,4}\)?[\s.\-]?){2,4}\d{3,4}"
)
CONTACT_PATH_HINTS = ("contact", "about", "team", "careers", "jobs", "get-in-touch")

BAD_EMAIL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
BAD_EMAIL_PREFIXES = ("example@", "you@", "name@", "sentry@", "wixpress.com")


def _get(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
            return resp.text
    except requests.RequestException:
        pass
    return None


def _find_contact_links(base_url: str, html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").lower()
        if any(hint in href.lower() or hint in text for hint in CONTACT_PATH_HINTS):
            links.add(urljoin(base_url, href))
    return list(links)[:3]  # keep it light — max 3 extra pages per site


def _extract_emails(html: str) -> set:
    found = set()
    for m in EMAIL_RE.findall(html):
        email = m.lower().strip(".")
        if email.endswith(BAD_EMAIL_SUFFIXES):
            continue
        if any(email.startswith(p) for p in BAD_EMAIL_PREFIXES):
            continue
        found.add(email)
    return found


def _extract_phones(html: str) -> set:
    found = set()
    for m in PHONE_RE.finditer(html):
        digits = re.sub(r"\D", "", m.group())
        if 9 <= len(digits) <= 15:
            found.add(m.group().strip())
    return found


def scrape_company_site(url: str, domain: str) -> dict:
    """
    Returns: {"emails": [...], "phones": [...], "pages_checked": [...]}
    """
    emails, phones, pages_checked = set(), set(), []

    home_html = _get(url)
    if not home_html:
        return {"emails": [], "phones": [], "pages_checked": []}

    pages_checked.append(url)
    emails |= _extract_emails(home_html)
    phones |= _extract_phones(home_html)

    for link in _find_contact_links(url, home_html):
        time.sleep(config.REQUEST_DELAY_SECONDS)
        html = _get(link)
        if html:
            pages_checked.append(link)
            emails |= _extract_emails(html)
            phones |= _extract_phones(html)

    # prefer emails that match the company's own domain (more likely official)
    ranked_emails = sorted(
        emails, key=lambda e: (domain not in e, e)
    )

    return {
        "emails": ranked_emails[:5],
        "phones": sorted(phones)[:5],
        "pages_checked": pages_checked,
    }
