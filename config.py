"""
Central configuration for the lead-hunter automation.
Edit COUNTRIES, QUERY_TEMPLATES and the daily budget numbers to taste.
"""

import os

# ---------------------------------------------------------------------------
# Countries to hunt in, in the order they'll be processed. The script works
# through one country until it's exhausted (or the daily budget runs out),
# then moves to the next automatically.
#
# Ordered highest-budget markets first (US, UAE, Switzerland, Australia,
# Canada, UK, then wealthy Europe) so the best-paying leads land in the
# Sheet earliest, with lower-priority markets processed after. Reorder or
# edit freely - just move a country up/down this list to change priority.
# ---------------------------------------------------------------------------
COUNTRIES = [
    # --- Tier 1: highest-paying markets ---
    "United States",
    "United Arab Emirates",
    "Switzerland",
    "Australia",
    "Canada",
    "United Kingdom",
    "Qatar",
    "Norway",
    # --- Tier 2: strong Europe ---
    "Ireland",
    "Netherlands",
    "Denmark",
    "Germany",
    "Sweden",
    "Luxembourg",
    "Singapore",
    # --- Tier 3: still solid, lower priority ---
    "France",
    "New Zealand",
    "Italy",
    "Spain",
    "South Africa",
]

# ---------------------------------------------------------------------------
# Search query templates. {country} is substituted at runtime.
# These are plain search-engine queries (free, no scraping of job boards
# directly — we only ever touch a company's own public website).
# ---------------------------------------------------------------------------
QUERY_TEMPLATES = [
    '"digital marketing agency" {country} contact',
    '"digital marketing agency" {country} "hiring" ("video editor" OR "graphic designer")',
    '"creative agency" {country} "video editor" jobs',
    '"video production company" {country} contact email',
    '"branding agency" {country} "graphic designer" careers',
    'social media marketing agency {country} "contact us"',
]

# How many result pages to pull per query (each ddgs page ~ 10-20 results)
RESULTS_PAGES_PER_QUERY = 3

# ---------------------------------------------------------------------------
# Free-tier daily budgets. Tune these down if you're getting rate-limited.
# The run stops cleanly once any limit is hit and picks up again tomorrow.
# ---------------------------------------------------------------------------
MAX_SEARCH_QUERIES_PER_DAY = 400     # raised after a clean full-budget test run
MAX_SITES_SCRAPED_PER_DAY = 800      # be polite to the sites we visit
REQUEST_DELAY_SECONDS = 2.0          # pause between outbound HTTP requests
MAX_RUNTIME_MINUTES = 15             # stop gracefully before GitHub's 20-min hard cutoff
RESPECT_ROBOTS_TXT = True            # skip a site's contact pages if its robots.txt disallows them

# ---------------------------------------------------------------------------
# Dedupe: catches the same company showing up under two domains
# (e.g. agency.com and agency.io) by comparing company names, not just
# domains. 0.0-1.0 similarity threshold - higher = stricter match required.
# ---------------------------------------------------------------------------
DEDUPE_NAME_SIMILARITY = 0.88

# ---------------------------------------------------------------------------
# Optional paid email verification. Leave blank to keep using the free
# MX-record check. Set these to upgrade to real deliverability scoring.
# Supported providers: "zerobounce" (get a free-tier key at zerobounce.net)
# ---------------------------------------------------------------------------
EMAIL_VERIFY_PROVIDER = os.environ.get("EMAIL_VERIFY_PROVIDER", "")
EMAIL_VERIFY_API_KEY = os.environ.get("EMAIL_VERIFY_API_KEY", "")

# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
STATE_FILE = "state.json"

# ---------------------------------------------------------------------------
# Google Sheets output
# ---------------------------------------------------------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")

# Two ways to provide the service account credentials - use whichever is
# easier for the environment you're running in:
#   - GOOGLE_SHEETS_CREDENTIALS_FILE: path to the downloaded .json key file
#     (simplest for local runs - no copy/paste of JSON needed)
#   - GOOGLE_SHEETS_CREDENTIALS_JSON: the full JSON key content as a string
#     (used for GitHub Actions, where it's pasted directly into a Secret)
GOOGLE_SHEETS_CREDENTIALS_FILE = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
GOOGLE_SHEETS_CREDENTIALS_JSON = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
SHEET_BATCH_SIZE = 20  # rows buffered before each write to Sheets

# ---------------------------------------------------------------------------
# Optional (not required): Google Programmable Search Engine, used only as
# a higher-quality fallback if you set these. Leave blank to run 100% free
# via duckduckgo_search (ddgs), which needs no signup or API key at all.
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")

# Roles we're trying to match on a company's site/contact page text
TARGET_ROLE_KEYWORDS = [
    "video editor", "video editing", "motion graphics", "graphic designer",
    "graphic design", "creative director", "art director", "video production",
]
