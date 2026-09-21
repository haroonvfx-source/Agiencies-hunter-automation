# Lead Hunter

Finds digital marketing / creative agencies (plus companies hiring video
editors & graphic designers) across a list of countries, pulls contact
emails + phone numbers off **each company's own public website**, does a
free best-effort email check, and writes everything into a Google Sheet
— one tab per country. Built to run daily via GitHub Actions, resuming
automatically where it left off when free-tier limits are hit.

## How it works
1. **Discovery** (`modules/discovery.py`) — searches for agencies per
   country using `ddgs` (free, no signup). No LinkedIn/job-board
   scraping — those violate ToS and get you blocked fast.
2. **Scraping** (`modules/scrape_contacts.py`) — visits the homepage +
   up to 3 likely contact/about pages of each company's *own* site and
   regex-extracts emails and phone numbers.
3. **Verification** (`modules/verify_email.py`) — free syntax + MX
   record check. This filters out junk/fake addresses but is **not** a
   guarantee of deliverability (true SMTP-level verification is a paid
   service — see "Upgrading" below).
4. **Output** (`modules/sheets_writer.py`) — batches rows into your
   Google Sheet, one worksheet tab per country.
5. **State** (`modules/state.py`) — `state.json` tracks exactly which
   country/query/page you're on and every domain already scraped, so a
   run that stops mid-way (budget reached) picks up seamlessly next time.

## One-time setup

### 1. Local Python environment
```bash
cd lead-hunter
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Google Sheet + service account (free)
1. Go to [Google Cloud Console](https://console.cloud.google.com/) →
   create a project → enable the **Google Sheets API**.
2. IAM & Admin → Service Accounts → Create → create a JSON key → download it.
3. Create a Google Sheet (or use an existing one) and copy its ID from
   the URL: `https://docs.google.com/spreadsheets/d/THIS_PART_IS_THE_ID/edit`
4. Click **Share** on the sheet and share it (Editor) with the service
   account's email, e.g. `lead-hunter@your-project.iam.gserviceaccount.com`
   — found inside the JSON key file as `"client_email"`.

### 3. Environment variables
Copy `.env.example` to `.env` and fill in `SPREADSHEET_ID` and the full
contents of the service account JSON key as
`GOOGLE_SHEETS_CREDENTIALS_JSON` (as one line/string). For local runs,
load them however you prefer (e.g. `python-dotenv`, or export them in
your shell before running).

### 4. Run it
```bash
python main.py
```
Each run works through the current country's search queries until it
hits the daily budget in `config.py`, then stops cleanly. Run it again
(same day or the next) and it continues exactly where it stopped.

## Automating it daily on GitHub
1. Push this folder to a GitHub repo.
2. In the repo: **Settings → Secrets and variables → Actions** → add:
   - `SPREADSHEET_ID`
   - `GOOGLE_SHEETS_CREDENTIALS_JSON`
   - (optional) `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`
3. The workflow at `.github/workflows/daily_lead_hunt.yml` runs every
   day at 06:00 UTC (edit the cron line to change that), and also
   commits the updated `state.json` back to the repo so progress
   survives across runs (GitHub Actions runners are thrown away after
   each run — without this commit step you'd restart from zero daily).
4. You can also trigger a run manually anytime from the **Actions** tab
   (`workflow_dispatch`).

## Tuning
Everything you'll want to tweak lives in `config.py`:
- `COUNTRIES` — order and list of countries to hunt in.
- `QUERY_TEMPLATES` — the search phrases used to find agencies/companies.
- `MAX_SEARCH_QUERIES_PER_DAY` / `MAX_SITES_SCRAPED_PER_DAY` — daily
  free-tier-friendly budget. Lower these if you get rate-limited by the
  search backend; raise them if you find you have headroom.
- `TARGET_ROLE_KEYWORDS` — used to flag which leads look like the best
  fit for video editor / graphic designer outreach.

To hunt again from scratch, delete `state.json` (or reset its
`country_index`/`seen_domains`).

## Feeding this into your outreach automation
Each country tab has columns: `company_domain, source_url, page_title,
country, emails, email_status, phones, matched_role_keywords,
date_found`. Your outreach script can read straight from these tabs via
the same `gspread` client, filtering on `email_status == "valid_domain"`
as a reasonable "safe to email" cutoff.

## Upgrading beyond the free tier (optional, later)
If lead quality/volume becomes the bottleneck:
- **Better search**: add `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` (Google
  Programmable Search, free up to 100 queries/day, paid beyond that) —
  the code already uses it automatically if set.
- **Real email verification**: swap `verify_email.py`'s MX check for a
  call to Hunter.io, NeverBounce, or ZeroBounce (all have small free
  tiers, then paid per-verification).
- **Richer company data**: Apollo.io or Clearbit APIs can add company
  size, LinkedIn URL, and named contacts (not just a generic inbox).

## A few things worth knowing
- This only ever scrapes companies' **own public websites** — not
  LinkedIn, Indeed, or other platforms with anti-scraping ToS, which
  keeps things both more reliable and lower-risk.
- Respect `robots.txt` and don't lower `REQUEST_DELAY_SECONDS` too far —
  being a polite, slow crawler is what keeps you from getting your IP
  blocked by the sites you visit.
- For B2B cold email once you use this data: UK/EU (PECR/GDPR),
  Australia (Spam Act), Canada (CASL), and the US (CAN-SPAM) all allow
  B2B outreach but require a working unsubscribe/opt-out and accurate
  sender info — worth baking into whatever sends the emails next.
