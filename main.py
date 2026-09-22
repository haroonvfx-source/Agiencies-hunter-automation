"""
Lead Hunter — finds digital marketing / creative agencies (and companies
hiring video editors & graphic designers) across a list of countries,
pulls contact emails + phone numbers off their own public websites, does
a free best-effort verification pass, and writes everything to Google
Sheets — one tab per country.

Designed to run as a daily GitHub Action. Each run works through search
queries for the *current* country until either that country's queries are
exhausted or today's free-tier budget (config.py) is used up, then stops
cleanly. state.json remembers exactly where it left off, so tomorrow's
run continues seamlessly — including moving on to the next country once
one is fully done.

Usage:
    python main.py
"""

import time
from datetime import datetime

import config
from modules import state as state_mod
from modules import discovery, scrape_contacts, verify_email
from modules.sheets_writer import SheetBatcher


def budget_left(state: dict) -> bool:
    return (
        state["queries_today"] < config.MAX_SEARCH_QUERIES_PER_DAY
        and state["sites_today"] < config.MAX_SITES_SCRAPED_PER_DAY
    )


def build_row(company: dict, contacts: dict, country: str) -> dict:
    emails = contacts["emails"]
    statuses = [verify_email.verify(e) for e in emails] if emails else []
    best_status = "no_email_found"
    if statuses:
        best_status = "valid_domain" if "valid_domain" in statuses else statuses[0]

    snippet_lower = (company.get("snippet", "") + company.get("title", "")).lower()
    matched_roles = [k for k in config.TARGET_ROLE_KEYWORDS if k in snippet_lower]

    return {
        "company_domain": company["domain"],
        "company_name": contacts.get("company_name", company["domain"]),
        "source_url": company["url"],
        "page_title": company.get("title", ""),
        "country": country,
        "emails": "; ".join(emails),
        "email_status": best_status,
        "phones": "; ".join(contacts["phones"]),
        "matched_role_keywords": ", ".join(matched_roles),
        "date_found": datetime.utcnow().strftime("%Y-%m-%d"),
        "outreach_status": "",  # your email automation can update this column
    }


def run():
    state = state_mod.load_state(config.STATE_FILE)

    if state["country_index"] >= len(config.COUNTRIES):
        print("All countries completed! Reset state.json (or extend "
              "config.COUNTRIES) to hunt again.")
        return

    country = config.COUNTRIES[state["country_index"]]
    print(f"=== Running for: {country} "
          f"(country {state['country_index'] + 1}/{len(config.COUNTRIES)}) ===")
    print(f"Budget today: {state['queries_today']}/{config.MAX_SEARCH_QUERIES_PER_DAY} "
          f"queries, {state['sites_today']}/{config.MAX_SITES_SCRAPED_PER_DAY} sites used so far")

    batcher = SheetBatcher(country)
    seen = set(state["seen_domains"])

    while budget_left(state):
        if state["query_index"] >= len(config.QUERY_TEMPLATES):
            # done with this country -> advance to the next one
            print(f"Finished all queries for {country}. Advancing to next country.")
            state["country_index"] += 1
            state["query_index"] = 0
            state["page_index"] = 0
            batcher.flush()
            state_mod.save_state(config.STATE_FILE, state)
            if state["country_index"] >= len(config.COUNTRIES):
                print("All countries completed for this cycle!")
                return
            country = config.COUNTRIES[state["country_index"]]
            batcher = SheetBatcher(country)
            print(f"=== Now running for: {country} ===")
            continue

        query_template = config.QUERY_TEMPLATES[state["query_index"]]
        query = query_template.format(country=country)
        page = state["page_index"] + 1

        print(f"[search] '{query}' (page {page})")
        companies = discovery.find_companies(query, page=page)
        state["queries_today"] += 1

        for company in companies:
            if not budget_left(state):
                break
            domain = company["domain"]
            if domain in seen:
                continue
            seen.add(domain)
            state_mod.mark_domain_seen(state, domain)

            print(f"  [scrape] {domain}")
            contacts = scrape_contacts.scrape_company_site(company["url"], domain)
            state["sites_today"] += 1

            if contacts["emails"] or contacts["phones"]:
                company_name = contacts.get("company_name", domain)
                if state_mod.is_duplicate_company_name(
                    state, company_name, config.DEDUPE_NAME_SIMILARITY
                ):
                    print(f"    -> skipped, looks like a duplicate of an "
                          f"already-found company ('{company_name}')")
                else:
                    row = build_row(company, contacts, country)
                    batcher.add(row)
                    state_mod.mark_company_name_seen(state, company_name)
                    print(f"    -> found {len(contacts['emails'])} email(s), "
                          f"{len(contacts['phones'])} phone(s)")

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
        state_mod.save_state(config.STATE_FILE, state)

    batcher.flush()
    state_mod.save_state(config.STATE_FILE, state)
    print("Daily budget reached — stopping cleanly. Resume tomorrow.")


if __name__ == "__main__":
    run()