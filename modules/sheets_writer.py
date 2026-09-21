"""
Writes lead rows to a Google Sheet — one worksheet tab per country, so
your later outreach automation can just read a clean tab per market.

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
    "company_domain", "source_url", "page_title", "country",
    "emails", "email_status", "phones", "matched_role_keywords",
    "date_found",
]


def _client():
    if config.GOOGLE_SHEETS_CREDENTIALS_FILE:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=SCOPES
        )
    else:
        creds_dict = json.loads(config.GOOGLE_SHEETS_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(sh, title: str):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=len(HEADER))
        ws.append_row(HEADER)
        return ws


class SheetBatcher:
    """Buffers rows and flushes them to the country's tab in one API call
    at a time, to stay well within Sheets' free quota (60 writes/min)."""

    def __init__(self, country: str):
        self.country = country
        self._buffer = []
        self._ws = None

    def _ensure_ws(self):
        if self._ws is None:
            gc = _client()
            sh = gc.open_by_key(config.SPREADSHEET_ID)
            self._ws = _get_or_create_worksheet(sh, self.country[:99])

    def add(self, row: dict):
        self._buffer.append([row.get(col, "") for col in HEADER])
        if len(self._buffer) >= config.SHEET_BATCH_SIZE:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        self._ensure_ws()
        self._ws.append_rows(self._buffer, value_input_option="RAW")
        print(f"  [sheets] wrote {len(self._buffer)} rows to '{self.country}' tab")
        self._buffer = []
