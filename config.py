"""
Central configuration for the lead-hunter automation.
Edit COUNTRIES, QUERY_TEMPLATES and the daily budget numbers to taste.
"""

import os

# ---------------------------------------------------------------------------
# Countries to hunt in, in the order they'll be processed. The script works
# through one country until it's exhausted (or the daily budget runs out),
# then moves to the next automatically. Add/remove/reorder freely.
# ---------------------------------------------------------------------------
COUNTRIES = [
    "United States",
    "United Kingdom",
    "United Arab Emirates",
    "Australia",
    "Canada",
    "Germany",
    "Netherlands",
    "Ireland",
    "Sweden",
    "France",
    "Spain",
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
MAX_SEARCH_QUERIES_PER_DAY = 80      # keeps well under free search limits
MAX_SITES_SCRAPED_PER_DAY = 250      # be polite to the sites we visit
REQUEST_DELAY_SECONDS = 2.0          # pause between outbound HTTP requests

# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
STATE_FILE = "state.json"

# ---------------------------------------------------------------------------
# Google Sheets output
# ---------------------------------------------------------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
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
