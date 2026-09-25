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
    "Saudi Arabia",
    "Hong Kong",
    "Bahrain",
    "Kuwait",
    "Japan",
    # --- Tier 2: strong Europe / Asia ---
    "Ireland",
    "Netherlands",
    "Denmark",
    "Germany",
    "Sweden",
    "Luxembourg",
    "Singapore",
    "Belgium",
    "Austria",
    "Finland",
    "South Korea",
    # --- Tier 3: still solid, lower priority ---
    "France",
    "New Zealand",
    "Italy",
    "Spain",
    "South Africa",
    "Portugal",
    "Poland",
    "Czech Republic",
    "Iceland",
    "Malta",
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
MAX_SEARCH_QUERIES_PER_DAY = 150     # raised after a clean full-budget test run
MAX_SITES_SCRAPED_PER_DAY = 400      # be polite to the sites we visit
REQUEST_DELAY_SECONDS = 2.0          # pause between outbound HTTP requests
RESPECT_ROBOTS_TXT = True            # skip a site's contact pages if its robots.txt disallows them
MAX_RUNTIME_MINUTES = 15             # hard stop per run; safety margin under the 20-min GitHub Actions job timeout

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

# ---------------------------------------------------------------------------
# Decision-maker extraction: job titles worth pulling a name for, so
# outreach can be addressed to a real person instead of a generic inbox.
# Best-effort - scraped from visible page text, not always found.
# ---------------------------------------------------------------------------
DECISION_MAKER_TITLES = [
    "creative director", "art director", "founder", "co-founder", "ceo",
    "owner", "managing director", "head of design", "head of video",
    "hiring manager", "talent acquisition", "hr manager", "studio manager",
    "executive producer", "production manager",
]

# ---------------------------------------------------------------------------
# Phone normalization: ISO 3166-1 alpha-2 codes for each country in
# COUNTRIES, used as a region hint so scraped phone numbers can be
# formatted into a consistent, dialable international format.
# ---------------------------------------------------------------------------
COUNTRY_ISO2 = {
    "United States": "US", "United Arab Emirates": "AE", "Switzerland": "CH",
    "Australia": "AU", "Canada": "CA", "United Kingdom": "GB", "Qatar": "QA",
    "Norway": "NO", "Ireland": "IE", "Netherlands": "NL", "Denmark": "DK",
    "Germany": "DE", "Sweden": "SE", "Luxembourg": "LU", "Singapore": "SG",
    "France": "FR", "New Zealand": "NZ", "Italy": "IT", "Spain": "ES",
    "South Africa": "ZA", "Saudi Arabia": "SA",
    "Hong Kong": "HK", "Bahrain": "BH", "Kuwait": "KW", "Japan": "JP",
    "Belgium": "BE", "Austria": "AT", "Finland": "FI", "South Korea": "KR",
    "Portugal": "PT", "Poland": "PL", "Czech Republic": "CZ",
    "Iceland": "IS", "Malta": "MT",
}

# ---------------------------------------------------------------------------
# Premium lead detection: companies mentioning visa sponsorship or remote
# work get flagged and copied into their own "Premium Leads" tab, since
# these tend to be the highest-quality leads for this kind of outreach.
# ---------------------------------------------------------------------------
PREMIUM_KEYWORDS = [
    "visa sponsorship", "sponsor visa", "visa sponsor", "sponsorship available",
    "relocation assistance", "relocation package", "remote work", "fully remote",
    "100% remote", "remote-first", "remote first", "work from home",
    "work remotely", "hybrid remote",
]

# ---------------------------------------------------------------------------
# Lead scoring: a simple points system so your outreach automation can
# work the best leads first. Higher score = better lead to email.
# ---------------------------------------------------------------------------
SCORE_VALID_EMAIL = 40          # has at least one MX-verified email
SCORE_DECISION_MAKER = 30       # found a named person + title to address
SCORE_PREMIUM = 20              # mentions visa sponsorship / remote work
SCORE_MATCHED_ROLE = 10         # page mentions video editor / graphic designer
