"""
Persists progress to a JSON file so the automation can stop mid-country
(e.g. free-tier limit reached) and pick up exactly where it left off,
including on a fresh GitHub Actions runner the next day.
"""

import json
import os
from datetime import date

DEFAULT_STATE = {
    "country_index": 0,        # which country in config.COUNTRIES we're on
    "query_index": 0,          # which query template we're on for that country
    "page_index": 0,           # which results page we're on for that query
    "seen_domains": [],        # domains already scraped, ever (avoid dupes)
    "seen_company_names": [],  # company names already written, for fuzzy dedupe
    "mx_cache": {},            # domain -> bool, persisted MX lookup results
    "query_stats": {},         # query template text -> cumulative leads found
    "cycle": 1,                # how many full passes through COUNTRIES we've completed
    "last_run_date": None,
    "queries_today": 0,
    "sites_today": 0,
    "errors_today": 0,
}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return dict(DEFAULT_STATE)
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Reset the daily counters if this is a new day
    today = date.today().isoformat()
    if state.get("last_run_date") != today:
        state["queries_today"] = 0
        state["sites_today"] = 0
        state["errors_today"] = 0
        state["last_run_date"] = today

    # backfill any keys missing from an older state file
    for k, v in DEFAULT_STATE.items():
        state.setdefault(k, v)
    return state


def save_state(path: str, state: dict) -> None:
    state["last_run_date"] = date.today().isoformat()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, path)


def mark_domain_seen(state: dict, domain: str) -> None:
    if domain not in state["seen_domains"]:
        state["seen_domains"].append(domain)


def is_duplicate_company_name(state: dict, name: str, threshold: float) -> bool:
    """Fuzzy-matches a company name against ones already written to the
    sheet, catching e.g. 'Acme Agency' on both acme.com and acme.io."""
    import difflib
    name_norm = name.strip().lower()
    if not name_norm:
        return False
    for seen in state["seen_company_names"]:
        if difflib.SequenceMatcher(None, name_norm, seen).ratio() >= threshold:
            return True
    return False


def mark_company_name_seen(state: dict, name: str) -> None:
    name_norm = name.strip().lower()
    if name_norm and name_norm not in state["seen_company_names"]:
        state["seen_company_names"].append(name_norm)
