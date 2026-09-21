"""
Finds candidate company websites for a search query.

Primary (fully free, no signup): duckduckgo_search (ddgs package).
Optional fallback (also free up to 100 queries/day): Google Custom Search
JSON API, used only if GOOGLE_API_KEY + GOOGLE_CSE_ID are set in config.

Returns a list of dicts: {"url": ..., "domain": ..., "title": ..., "snippet": ...}
"""

import time
from urllib.parse import urlparse

import requests

import config


def _domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _is_junk_domain(domain: str) -> bool:
    junk = (
        "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
        "youtube.com", "indeed.com", "glassdoor.com", "wikipedia.org",
        "yelp.com", "google.com", "pinterest.com", "tiktok.com", "clutch.co",
    )
    return any(j in domain for j in junk)


def search_ddg(query: str, max_results: int = 15) -> list:
    """Free, no-key search via the ddgs package."""
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # older package name

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                url = r.get("href") or r.get("url") or ""
                domain = _domain_of(url)
                if not url or not domain or _is_junk_domain(domain):
                    continue
                results.append({
                    "url": url,
                    "domain": domain,
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
    except Exception as e:
        print(f"  [discovery] ddgs search failed for '{query}': {e}")
    return results


def search_google_cse(query: str, page: int = 1) -> list:
    """Optional fallback using Google Programmable Search (free up to 100/day)."""
    if not (config.GOOGLE_API_KEY and config.GOOGLE_CSE_ID):
        return []
    start = (page - 1) * 10 + 1
    params = {
        "key": config.GOOGLE_API_KEY,
        "cx": config.GOOGLE_CSE_ID,
        "q": query,
        "start": start,
    }
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1", params=params, timeout=15
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as e:
        print(f"  [discovery] Google CSE failed for '{query}': {e}")
        return []

    results = []
    for it in items:
        url = it.get("link", "")
        domain = _domain_of(url)
        if not url or not domain or _is_junk_domain(domain):
            continue
        results.append({
            "url": url,
            "domain": domain,
            "title": it.get("title", ""),
            "snippet": it.get("snippet", ""),
        })
    return results


def find_companies(query: str, page: int) -> list:
    """
    Single entry point used by main.py. Tries free DDG search first; if
    Google CSE credentials are configured, merges those results in too.
    """
    results = search_ddg(query, max_results=20)
    time.sleep(1)
    results += search_google_cse(query, page=page)

    # de-dupe by domain, preserve order
    seen, deduped = set(), []
    for r in results:
        if r["domain"] in seen:
            continue
        seen.add(r["domain"])
        deduped.append(r)
    return deduped
