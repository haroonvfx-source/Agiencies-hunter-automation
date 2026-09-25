"""
Lead Hunter — finds digital marketing / creative agencies (and companies
hiring video editors & graphic designers) across a list of countries,
pulls contact emails + phone numbers off their own public websites, does
a free best-effort verification pass, and writes everything to Google
Sheets — one tab per country, plus a "Premium Leads" tab for companies
mentioning visa sponsorship or remote work.

Designed to run as a daily GitHub Action. Each run works through search
queries for the *current* country until either that country's queries are
exhausted, today's free-tier budget (config.py) is used up, or the
per-run time limit is reached, then stops cleanly. state.json remembers
exactly where it left off, so the next run continues seamlessly —
including moving on to the next country once one is fully done.

Usage:
    python main.py
"""

import sys
import time
import traceback
from datetime import datetime

import config
from modules import state as state_mod
from modules import discovery, scrape_contacts, verify_email, phone_utils
from modules.sheets_writer import SheetBatcher, PREMIUM_TAB_NAME
from modules import sheets_writer


def budget_left(state: dict) -> bool:
    return (
        state["queries_today"] < config.MAX_SEARCH_QUERIES_PER_DAY
        and state["sites_today"] < config.MAX_SITES_SCRAPED_PER_DAY
    )


def build_row(company: dict, contacts: dict, country: str, state: dict) -> dict:
    emails = contacts["emails"]
    statuses = [verify_email.verify(e, state["mx_cache"]) for e in emails] if emails else []
    best_status = "no_email_found"
    if statuses:
        best_status = "valid_domain" if "valid_domain" in statuses else statuses[0]

    snippet_lower = (company.get("snippet", "") + company.get("title", "")).lower()
    matched_roles = [k for k in config.TARGET_ROLE_KEYWORDS if k in snippet_lower]

    normalized_phones = phone_utils.normalize_phones(contacts["phones"], country)

    lead_score = 0
    if best_status == "valid_domain":
        lead_score += config.SCORE_VALID_EMAIL
    if contacts.get("contact_name"):
        lead_score += config.SCORE_DECISION_MAKER
    if contacts.get("premium_flags"):
        lead_score += config.SCORE_PREMIUM
    if matched_roles:
        lead_score += config.SCORE_MATCHED_ROLE

    return {
        "company_domain": company["domain"],
        "company_name": contacts.get("company_name", company["domain"]),
        "contact_name": contacts.get("contact_name", ""),
        "contact_title": contacts.get("contact_title", ""),
        "lead_score": lead_score,
        "source_url": company["url"],
        "page_title": company.get("title", ""),
        "country": country,
        "emails": "; ".join(emails),
        "email_status": best_status,
        "phones": "; ".join(normalized_phones),
        "matched_role_keywords": ", ".join(matched_roles),
        "premium_flags": ", ".join(contacts.get("premium_flags", [])),
        "date_found": datetime.utcnow().strftime("%Y-%m-%d"),
        "outreach_status": "",  # your email automation can update this column
    }


def run():
    start_time = time.time()

    def time_left():
        return (time.time() - start_time) < config.MAX_RUNTIME_MINUTES * 60

    state = state_mod.load_state(config.STATE_FILE)

    # run-level counters, reset every run, used for the Run Summary row
    queries_at_start = state["queries_today"]
    sites_at_start = state["sites_today"]
    leads_this_run = 0
    premium_this_run = 0
    errors_this_run = 0

    if state["country_index"] >= len(config.COUNTRIES):
        # Finished every country in a previous run - start a fresh cycle.
        # Companies already found are NEVER re-added (seen_domains blocks
        # that permanently, protecting outreach_status from duplicates) -
        # this just re-runs the searches to catch newly-appeared companies.
        state["cycle"] = state.get("cycle", 1) + 1
        state["country_index"] = 0
        state["query_index"] = 0
        state["page_index"] = 0
        print(f"All countries completed! Starting cycle {state['cycle']} "
              f"to look for newly-appeared companies.")

    run_start_country = config.COUNTRIES[state["country_index"]]
    country = run_start_country
    print(f"=== Running for: {country} (country {state['country_index'] + 1}/"
          f"{len(config.COUNTRIES)}, cycle {state.get('cycle', 1)}) ===")
    print(f"Budget today: {state['queries_today']}/{config.MAX_SEARCH_QUERIES_PER_DAY} "
          f"queries, {state['sites_today']}/{config.MAX_SITES_SCRAPED_PER_DAY} sites used so far")

    batcher = SheetBatcher(country)
    premium_batcher = SheetBatcher(PREMIUM_TAB_NAME)
    seen = set(state["seen_domains"])

    while budget_left(state) and time_left():
        if state["query_index"] >= len(config.QUERY_TEMPLATES):
            # done with this country -> advance to the next one
            print(f"Finished all queries for {country}. Advancing to next country.")
            state["country_index"] += 1
            state["query_index"] = 0
            state["page_index"] = 0
            batcher.flush()
            state_mod.save_state(config.STATE_FILE, state)
            if state["country_index"] >= len(config.COUNTRIES):
                state["cycle"] = state.get("cycle", 1) + 1
                state["country_index"] = 0
                print(f"All countries completed! Starting cycle {state['cycle']} "
                      f"to look for newly-appeared companies.")
            country = config.COUNTRIES[state["country_index"]]
            batcher = SheetBatcher(country)
            print(f"=== Now running for: {country} (cycle {state['cycle']}) ===")
            continue

        query_template = config.QUERY_TEMPLATES[state["query_index"]]
        query = query_template.format(country=country)
        page = state["page_index"] + 1

        print(f"[search] '{query}' (page {page})")
        try:
            companies = discovery.find_companies(query, page=page)
        except Exception as e:
            print(f"  [search] error, skipping this query/page: {e}")
            companies = []
            state["errors_today"] += 1
            errors_this_run += 1
        state["queries_today"] += 1

        for company in companies:
            if not (budget_left(state) and time_left()):
                break
            domain = company["domain"]
            if domain in seen:
                continue
            seen.add(domain)
            state_mod.mark_domain_seen(state, domain)

            print(f"  [scrape] {domain}")
            try:
                contacts = scrape_contacts.scrape_company_site(company["url"], domain)
            except Exception as e:
                print(f"    -> error scraping {domain}, skipping: {e}")
                state["errors_today"] += 1
                errors_this_run += 1
                continue
            state["sites_today"] += 1

            if contacts["emails"] or contacts["phones"]:
                company_name = contacts.get("company_name", domain)
                if state_mod.is_duplicate_company_name(
                    state, company_name, config.DEDUPE_NAME_SIMILARITY
                ):
                    print(f"    -> skipped, looks like a duplicate of an "
                          f"already-found company ('{company_name}')")
                else:
                    row = build_row(company, contacts, country, state)
                    batcher.add(row)
                    state_mod.mark_company_name_seen(state, company_name)
                    leads_this_run += 1
                    state["query_stats"][query_template] = (
                        state["query_stats"].get(query_template, 0) + 1
                    )

                    premium_note = ""
                    if row["premium_flags"]:
                        premium_batcher.add(row)
                        premium_this_run += 1
                        premium_note = f" [PREMIUM: {row['premium_flags']}]"

                    contact_note = (
                        f", contact: {row['contact_name']} ({row['contact_title']})"
                        if row["contact_name"] else ""
                    )
                    print(f"    -> found {len(contacts['emails'])} email(s), "
                          f"{len(contacts['phones'])} phone(s){contact_note}{premium_note}")

            time.sleep(config.REQUEST_DELAY_SECONDS)

        # advance pagination / query pointer
        if page >= config.RESULTS_PAGES_PER_QUERY:
            state["query_index"] += 1
            state["page_index"] = 0
        else:
            state["page_index"] += 1

        # save progress after every query so a crash never loses more
        # than one query's worth of work
        batcher.flush()
        premium_batcher.flush()
        state_mod.save_state(config.STATE_FILE, state)

    batcher.flush()
    premium_batcher.flush()
    state_mod.save_state(config.STATE_FILE, state)

    if not time_left():
        print("Time limit for this run reached — stopping cleanly. Next scheduled run continues from here.")
    else:
        print("Daily budget reached — stopping cleanly. Resume tomorrow.")

    # write this run's summary + the updated query-performance rollup
    sheets_writer.write_run_summary({
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cycle": state.get("cycle", 1),
        "country": run_start_country,
        "leads_found": leads_this_run,
        "premium_leads_found": premium_this_run,
        "sites_scraped": state["sites_today"] - sites_at_start,
        "queries_used": state["queries_today"] - queries_at_start,
        "errors": errors_this_run,
    })
    sheets_writer.write_query_performance(state["query_stats"])


if __name__ == "__main__":
    try:
        run()
    except Exception:
        # print a full traceback and exit non-zero so the GitHub Actions
        # job shows as Failed - by default GitHub emails the repo owner
        # when a scheduled workflow run fails, so this doubles as a free
        # failure alert with no extra setup needed.
        traceback.print_exc()
        sys.exit(1)
