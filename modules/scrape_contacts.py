"""
Visits a company's own public website (homepage + likely contact/about
pages only — never LinkedIn, job boards, or anything behind a login) and
extracts emails, phone numbers, and a company name guess.
"""

import re
import time
import urllib.robotparser
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import phonenumbers

import config

_robots_cache = {}

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


def _robots_allows(url: str) -> bool:
    if not config.RESPECT_ROBOTS_TXT:
        return True
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(origin, "/robots.txt"))
        try:
            # RobotFileParser.read() uses urlopen() with NO timeout, which can
            # hang forever on a slow/dead server. Fetch it ourselves with a
            # timeout and hand the text to parse() instead.
            resp = requests.get(rp.url, headers=HEADERS, timeout=8)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp = None  # non-200 (404 etc.) -> default to allowing
        except Exception:
            rp = None  # if robots.txt can't be fetched, default to allowing
        _robots_cache[origin] = rp
    rp = _robots_cache[origin]
    if rp is None:
        return True
    try:
        return rp.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return True


NAME_RE = re.compile(r"^[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2}$")

# Capitalised business/legal/UI words that are never part of a person's name.
# If any word of a candidate is in here it is rejected ("Copyright Assignment",
# "Product Marketing", "IT Support" ...). Add words here to tighten further.
NOT_A_NAME_WORDS = {
    "copyright", "assignment", "product", "marketing", "support", "services",
    "service", "team", "studio", "studios", "agency", "company", "group",
    "design", "designer", "digital", "creative", "media", "video", "content",
    "sales", "business", "management", "manager", "director", "officer",
    "president", "vice", "senior", "junior", "assistant", "operations",
    "human", "resources", "customer", "success", "engineering", "technology",
    "solutions", "consulting", "contact", "about", "careers", "jobs", "news",
    "blog", "privacy", "policy", "terms", "conditions", "rights", "reserved",
    "read", "more", "learn", "our", "the", "and", "for", "with", "get", "started",
    "it", "hr", "ceo", "cto", "cfo", "coo", "owner", "founder", "head",
}


def _looks_like_person(name: str) -> bool:
    words = [w.lower() for w in name.replace("-", " ").split()]
    return bool(words) and not any(w in NOT_A_NAME_WORDS for w in words)


def _extract_decision_maker(html: str) -> tuple:
    """Best-effort scan of visible page text for a named person next to a
    decision-maker job title (e.g. 'Jane Smith - Creative Director').
    Returns (name, title) or ("", "") if nothing plausible is found."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()][:400]

    for i, line in enumerate(lines):
        low = line.lower()
        if len(line) > 80:
            continue
        for title in config.DECISION_MAKER_TITLES:
            if not re.search(r"\b" + re.escape(title) + r"\b", low):
                continue
            # try same line split on separators, then neighbouring lines
            candidates = re.split(r"[-,|]", line) + [
                lines[i - 1] if i > 0 else "",
                lines[i + 1] if i + 1 < len(lines) else "",
            ]
            for cand in candidates:
                cand = cand.strip()
                if (cand and title not in cand.lower() and NAME_RE.match(cand)
                        and _looks_like_person(cand)):
                    return cand, title.title()
    return "", ""


def _extract_premium_flags(html: str) -> list:
    """Flags companies mentioning visa sponsorship or remote work - these
    tend to be the highest-quality leads for this kind of outreach."""
    text_lower = BeautifulSoup(html, "html.parser").get_text(" ").lower()
    return [kw for kw in config.PREMIUM_KEYWORDS if kw in text_lower]


def _extract_company_name(html: str, domain: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        return og_site["content"].strip()
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        # titles are often "Company Name | Tagline" or "Company - Tagline"
        for sep in (" | ", " – ", " — ", " - "):
            if sep in title:
                return title.split(sep)[0].strip()
        return title[:80]
    return domain


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


DATE_RE = re.compile(
    r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"
)


def _valid_phone(raw: str, region, from_tel_link: bool = False) -> bool:
    """A number is kept only if the phonenumbers library says it is a real,
    dialable number for the lead's country (or carries an explicit +CC).
    Timestamps, IDs and dates fail this check. An explicit tel: link is
    trusted a bit more (any 7-15 digit number)."""
    digits = re.sub(r"\D", "", raw)
    if not 7 <= len(digits) <= 15:
        return False
    try:
        parsed = phonenumbers.parse(raw, region)
        if phonenumbers.is_valid_number(parsed):
            return True
    except phonenumbers.NumberParseException:
        pass
    return from_tel_link


def _extract_phones(html: str, region=None) -> list:
    """Phones from tel: links first, then visible page text only (scripts,
    styles and attributes are ignored, so timestamps/IDs are not picked up).
    Returns an ordered, de-duplicated list."""
    soup = BeautifulSoup(html, "html.parser")
    ordered, seen_digits = [], set()

    def add(raw, from_tel=False):
        raw = raw.strip()
        digits = re.sub(r"\D", "", raw)
        if digits in seen_digits or not _valid_phone(raw, region, from_tel):
            return
        seen_digits.add(digits)
        ordered.append(raw)

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("tel:"):
            add(unquote(href[4:]).split(";")[0], from_tel=True)

    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = DATE_RE.sub(" ", soup.get_text(" "))
    for m in PHONE_RE.finditer(text):
        add(m.group())
    return ordered


def scrape_company_site(url: str, domain: str, country: str = None) -> dict:
    """
    Returns: {"emails": [...], "phones": [...], "pages_checked": [...],
              "company_name": str, "contact_name": str, "contact_title": str,
              "premium_flags": [...], "status": "ok"|"robots_blocked"|"fetch_failed"}
    """
    empty_result = {
        "emails": [], "phones": [], "pages_checked": [], "company_name": domain,
        "contact_name": "", "contact_title": "", "premium_flags": [],
        "status": "fetch_failed",   # ok | robots_blocked | fetch_failed
    }

    region = config.COUNTRY_ISO2.get(country) if country else None
    emails, phones, pages_checked = set(), [], []
    contact_name, contact_title = "", ""
    premium_flags = set()

    if not _robots_allows(url):
        # a deliberate "no" from the site - final, never worth retrying
        return {**empty_result, "status": "robots_blocked"}

    home_html = _get(url)
    if not home_html:
        return empty_result

    pages_checked.append(url)
    emails |= _extract_emails(home_html)
    phones += _extract_phones(home_html, region)
    company_name = _extract_company_name(home_html, domain)
    contact_name, contact_title = _extract_decision_maker(home_html)
    premium_flags |= set(_extract_premium_flags(home_html))

    for link in _find_contact_links(url, home_html):
        if not _robots_allows(link):
            continue
        time.sleep(config.REQUEST_DELAY_SECONDS)
        html = _get(link)
        if html:
            pages_checked.append(link)
            emails |= _extract_emails(html)
            phones += _extract_phones(html, region)
            premium_flags |= set(_extract_premium_flags(html))
            if not contact_name:
                contact_name, contact_title = _extract_decision_maker(html)

    # prefer emails that match the company's own domain (more likely official)
    ranked_emails = sorted(
        emails, key=lambda e: (domain not in e, e)
    )

    return {
        "emails": ranked_emails[:5],
        "phones": list(dict.fromkeys(phones))[:5],
        "pages_checked": pages_checked,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_title": contact_title,
        "premium_flags": sorted(premium_flags),
        "status": "ok",
    }
