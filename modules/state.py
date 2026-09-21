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
    "last_run_date": None,
    "queries_today": 0,
    "sites_today": 0,
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
