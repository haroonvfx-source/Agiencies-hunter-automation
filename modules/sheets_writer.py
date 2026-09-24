"""
Writes lead rows to a Google Sheet — one worksheet tab per country, plus
three extra tabs the automation maintains automatically:
  - "Premium Leads"    - companies mentioning visa sponsorship or remote
                          work, copied here in addition to their country tab
  - "Run Summary"       - one row appended per run: what it found, how
                          much budget it used, whether anything errored
  - "Query Performance" - cumulative lead count per search query template,
                          so you can see which queries are worth keeping

Setup (all free):
  1. Google Cloud Console -> new project -> enable "Google Sheets API".
  2. Create a Service Account -> create a JSON key -> download it.
  3. Create/open your target Google Sheet, click Share, and share it
     (Editor access) with the service account's email address
     (looks like xxx@xxx.iam.gserviceaccount.com).
  4. Put the full JSON key contents into the GOOGLE_SHEETS_CREDENTIALS_JSON
     environment variable (or GitHub secret), and the sheet's ID (the long
     id in its URL) into SPREADSHEET_ID.
"""

import json

import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADER = [
    "company_domain", "company_name", "contact_name", "contact_title",
    "source_url", "page_title", "country",
    "emails", "email_status", "phones", "matched_role_keywords",
    "premium_flags", "date_found", "outreach_status",
]

RUN_SUMMARY_HEADER = [
    "timestamp_utc", "country", "leads_found", "premium_leads_found",
    "sites_scraped", "queries_used", "errors",
]

QUERY_PERF_HEADER = ["query_template", "cumulative_leads_found"]

PREMIUM_TAB_NAME = "Premium Leads"


def _client():
    if config.GOOGLE_SHEETS_CREDENTIALS_FILE:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=SCOPES
        )
    else:
        creds_dict = json.loads(config.GOOGLE_SHEETS_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(sh, title: str, header: list = None):
    header = header or HEADER
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(len(header), 1))
        ws.append_row(header)
        return ws


class SheetBatcher:
    """Buffers rows and flushes them to a tab in one API call at a time,
    to stay well within Sheets' free quota (60 writes/min). Used both for
    per-country tabs and the "Premium Leads" tab."""

    def __init__(self, tab_name: str):
        self.tab_name = tab_name
        self._buffer = []
        self._ws = None

    def _ensure_ws(self):
        if self._ws is None:
            gc = _client()
            sh = gc.open_by_key(config.SPREADSHEET_ID)
            self._ws = _get_or_create_worksheet(sh, self.tab_name[:99])

    def add(self, row: dict):
        self._buffer.append([row.get(col, "") for col in HEADER])
        if len(self._buffer) >= config.SHEET_BATCH_SIZE:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        self._ensure_ws()
        self._ws.append_rows(self._buffer, value_input_option="RAW")
        print(f"  [sheets] wrote {len(self._buffer)} rows to '{self.tab_name}' tab")
        self._buffer = []


def write_run_summary(stats: dict):
    """Appends one row to the 'Run Summary' tab describing this run."""
    gc = _client()
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    ws = _get_or_create_worksheet(sh, "Run Summary", RUN_SUMMARY_HEADER)
    row = [
        stats.get("timestamp", ""),
        stats.get("country", ""),
        stats.get("leads_found", 0),
        stats.get("premium_leads_found", 0),
        stats.get("sites_scraped", 0),
        stats.get("queries_used", 0),
        stats.get("errors", 0),
    ]
    ws.append_row(row, value_input_option="RAW")
    print("  [sheets] wrote run summary row")


def write_query_performance(query_stats: dict):
    """Overwrites the 'Query Performance' tab with current cumulative
    totals per query template, ranked best to worst."""
    if not query_stats:
        return
    gc = _client()
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    ws = _get_or_create_worksheet(sh, "Query Performance", QUERY_PERF_HEADER)
    ws.clear()
    ws.append_row(QUERY_PERF_HEADER)
    rows = [[q, n] for q, n in sorted(query_stats.items(), key=lambda x: -x[1])]
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
    print("  [sheets] wrote query performance summary")
