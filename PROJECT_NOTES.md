# FinSight: Project Notes

> **Status:** Milestone 1 complete (25 Oct 2026). Next: Milestone 2, curated dataset + validation.
> This file is the single reference for how the project is built. It is updated at the end of every milestone.

---

## 1. What FinSight does

FinSight is a financial research tool that compares three listed Indian paint companies over five financial years. It does three things:

1. **Shows verified numbers.** Figures are taken from the consolidated financial statements in each annual report and stored with their source page. Metrics are then calculated by Python and SQL.
2. **Answers questions about the filings.** It searches the annual report text and answers with citations (document plus page). It says so when it cannot find evidence.
3. **Writes an analyst brief.** Python fills in every number. The AI model only writes the commentary, and every claim it makes must cite a passage.

**Core rule:** the AI model never does arithmetic and never introduces a number. Every number comes from the database.

---

## 2. Scope (minimum viable version)

| Item | Decision |
|---|---|
| Companies | Asian Paints, Berger Paints India, Kansai Nerolac Paints |
| Years | FY2022 to FY2026 (years ending 31 March), plus FY2021 balance sheet for average-equity ratios |
| Basis | Consolidated statements, Ind AS |
| Units | Stored in ₹ crore. Values reported in other units are converted on load, and the original unit is recorded |
| Documents for search | All 15 annual reports (3 companies × 5 years) |
| Out of scope for now | Quarterly results, more companies, automated table extraction, deployment, chat memory |

Why the paints sector:
- All three companies have the same year end (31 March), the same accounting standard and similar business models, so the comparison is fair.
- **The story:** Grasim launched Birla Opus in February 2024, and that entry sits in the middle of the five-year window. That makes questions like "What did management say about competition, and did margins or dealer credit change?" answerable from both the numbers and the text.
- **Real data issues to handle:** Kansai Nerolac's ₹726 crore Mumbai land sale created a one-off gain in **FY2025**: its cash flow statement shows a ₹665.44 crore adjustment for the asset sale, and profit before tax falls from ₹1,478 crore (FY2025) to ₹797 crore (FY2026). This will be confirmed against the exceptional-items line in Milestone 2. Nerolac also has a larger industrial and automotive business than the other two. Handling both is good evidence of careful data work.
- All 15 annual reports (FY2022–FY2026) are downloaded and verified (Milestone 1).

---

## 3. Architecture

```
 Annual report PDFs (official IR sites / BSE)
        │
        ├──► [A] Manual curation of statement figures ──► reported_values.csv (value + page ref)
        │                                                      │
        │                                         validation.py (checks, see §7)
        │                                                      │
        │                                              SQLite: finsight.db
        │                                                      │
        │                                   metrics.py (Python formulas) ──► metrics table
        │                                                      │
        └──► [B] pdf_ingest.py: page text ──► chunks ──► embeddings (local model)
                                                               │
                                                       retrieval.py (cosine search)
                                                               │
                         llm.py (Gemini): answer only from retrieved passages
                                    + verified figures table from SQLite
                                                               │
                                     Streamlit app (4 pages) + Plotly charts
```

The two sides are independent. If the Gemini API is down or out of quota, pages 1 and 2 (numbers and charts) still work fully, and page 3 still shows the retrieved passages. Only the written answer is missing.

**Why manual curation instead of automatic table extraction?** There are about 20 line items × 3 companies × 6 years, which is roughly 360 numbers. Entering them by hand with automated checks is more reliable than parsing tables out of 300-page PDFs, where errors are often silent. Automated extraction is a stretch goal, measured against the hand-entered values (for example "the extractor matched 93% of hand-verified values"), which would give a real result to report.

---

## 4. Tech stack

| Purpose | Tool | Why |
|---|---|---|
| Language | Python 3.12 or newer | Main language |
| Tables | pandas | Cleaning and analysis |
| Database | SQLite (built into Python) | One file, nothing to install |
| PDF text | PyMuPDF (`pymupdf`) | Fast, gives text page by page |
| Embeddings | `fastembed` with `BAAI/bge-small-en-v1.5` | Runs locally and free, no API key, no PyTorch install |
| Vector store | NumPy array saved as `.npy` + chunk text in SQLite | A few thousand chunks don't need a vector database. Search is about 5 lines you can explain |
| LLM | Google Gemini API, free tier (`google-genai` package) | Free tier with no card. Model name is a setting in `.env`, because Google retires models often |
| App | Streamlit + Plotly | Simple multi-page app with interactive charts |
| Tests | pytest | Standard and simple |
| Secrets | `.env` file read by `python-dotenv`. `.env` is never committed | API key stays off GitHub |

No LangChain, no agents, no cloud database.

---

## 5. Folder structure

```
FinSight_App_Project/
├── README.md                  # problem, data, method, setup, limitations
├── PROJECT_NOTES.md           # this file
├── requirements.txt           # pinned dependencies (added milestone by milestone)
├── pytest.ini                 # tells pytest where the code and tests are
├── .env.example               # template: GEMINI_API_KEY=..., GEMINI_MODEL=...
├── .gitignore                 # ignores .env, PDFs, database, embeddings
├── app.py                     # Streamlit home page = Research Overview
├── pages/
│   ├── 1_Company_Comparison.py
│   ├── 2_Ask_the_Filings.py
│   └── 3_Analyst_Brief.py
├── finsight/                  # the project's own code
│   ├── config.py              # paths and settings in one place
│   ├── documents.py           # load the report register, check PDFs and statement pages
│   ├── database.py            # create tables, load CSVs into SQLite
│   ├── validation.py          # data checks (see §7)
│   ├── metrics.py             # every formula, one function each
│   ├── queries.py             # SQL queries used by the app
│   ├── pdf_ingest.py          # PDF → page text → chunks
│   ├── retrieval.py           # embed chunks, search by similarity
│   ├── llm.py                 # Gemini calls, prompts, offline fallback
│   └── brief.py               # analyst brief assembly
├── sql/
│   └── schema.sql             # table definitions
├── data/
│   ├── reports/               # the 15 PDFs, e.g. berger_FY2025.pdf (not committed)
│   ├── curated/               # hand-entered CSVs (committed: these are the dataset)
│   │   ├── companies.csv
│   │   ├── documents.csv
│   │   ├── line_items.csv
│   │   └── reported_values.csv
│   └── processed/             # finsight.db, embeddings.npy (rebuilt by scripts)
├── scripts/
│   ├── check_documents.py     # Milestone 1: confirm all PDFs exist and open
│   ├── build_database.py      # CSVs → validated SQLite + metrics
│   ├── build_index.py         # PDFs → chunks → embeddings
│   └── run_eval.py            # runs the evaluation question set
├── eval/
│   ├── questions.csv          # questions, expected answers, expected pages
│   └── results/               # dated evaluation outputs
├── tests/
│   ├── test_documents.py      # Milestone 1
│   ├── test_line_items.py     # Milestone 1
│   ├── test_validation.py
│   ├── test_metrics.py
│   ├── test_queries.py
│   └── test_retrieval.py
└── docs/
    ├── case_study.md
    └── screenshots/
```

---

## 6. Database schema (SQLite)

```sql
companies (
  company_id      TEXT PRIMARY KEY,   -- 'ASIANPAINT', 'BERGEPAINT', 'KANSAINER' (NSE symbols)
  name            TEXT NOT NULL,
  fiscal_year_end TEXT NOT NULL,      -- '03-31'
  reporting_basis TEXT NOT NULL       -- 'Consolidated, Ind AS'
)

documents (
  document_id     TEXT PRIMARY KEY,   -- 'ASIANPAINT_FY2026_AR'
  company_id      TEXT REFERENCES companies,
  fiscal_year     INTEGER NOT NULL,   -- 2026 = year ending 31 Mar 2026
  doc_type        TEXT NOT NULL,      -- 'annual_report'
  file_name       TEXT NOT NULL,
  source_url      TEXT NOT NULL,
  downloaded_on   TEXT,
  page_count      INTEGER,
  sha256          TEXT,               -- fingerprint: proves the file is unchanged
  layout          TEXT,               -- 'single_page' or 'two_pages_per_sheet'
  bs_page         INTEGER,            -- first PDF page of consolidated balance sheet
  pl_page         INTEGER,            -- first PDF page of consolidated P&L
  cf_page         INTEGER,            -- first PDF page of consolidated cash flow
  unit_as_reported TEXT,              -- 'INR crore' for all 15 reports
  notes           TEXT
)

line_items (                          -- the dictionary of canonical items
  item_code       TEXT PRIMARY KEY,   -- 'revenue_from_operations'
  statement       TEXT NOT NULL,      -- 'PL' | 'BS' | 'CF'
  label           TEXT NOT NULL,      -- 'Revenue from operations'
  definition      TEXT NOT NULL,
  sign_convention TEXT                -- e.g. 'capex stored as positive outflow'
)

reported_values (
  company_id      TEXT REFERENCES companies,
  fiscal_year     INTEGER,
  item_code       TEXT REFERENCES line_items,
  value_cr        REAL,               -- NULL = genuinely not available (never 0 by default)
  unit_as_reported TEXT,              -- '₹ crore' / '₹ lakh' / '₹ million'
  label_as_reported TEXT,             -- exact wording in the report
  document_id     TEXT REFERENCES documents,
  page            INTEGER,            -- PDF page number (not the printed page number)
  note            TEXT,               -- e.g. 'restated in FY2025 report'
  PRIMARY KEY (company_id, fiscal_year, item_code)
)

metric_definitions (
  metric_code     TEXT PRIMARY KEY,   -- 'ebitda_margin'
  name            TEXT,
  formula         TEXT,               -- human-readable formula
  unit            TEXT                -- '%', 'x', 'days', '₹ crore'
)

metrics (
  company_id      TEXT,
  fiscal_year     INTEGER,
  metric_code     TEXT REFERENCES metric_definitions,
  value           REAL,               -- NULL with reason if inputs are missing
  null_reason     TEXT,
  PRIMARY KEY (company_id, fiscal_year, metric_code)
)

chunks (                              -- text pieces used for search
  chunk_id        INTEGER PRIMARY KEY,-- row number in embeddings.npy
  document_id     TEXT REFERENCES documents,
  page            INTEGER,
  text            TEXT
)
```

**Three kinds of figure, kept separate:** reported values (from the filing, with page), derived metrics (calculated by code, with formula), and interpretation (AI-written text, which must cite passages). The app labels each one.

---

## 7. Line items and metrics

**Line items to collect (consolidated):** 29 items, each defined with its sign convention in `data/curated/line_items.csv`.
P&L: revenue from operations, other income, cost of materials consumed, purchases of stock-in-trade, change in inventories, employee costs, other expenses, depreciation, finance costs, share of profit of associates/JVs, exceptional items, profit before tax, tax expense, profit for the year, profit attributable to owners.
Balance sheet: total equity, equity attributable to owners, borrowings (current and non-current, excluding lease liabilities), cash and cash equivalents, other bank balances, current investments, inventories, trade receivables, trade payables, total assets, total equity and liabilities.
Cash flow: net cash from operating activities, capital expenditure.

**Metrics (Python, one function each, all tested):**

| Metric | Formula |
|---|---|
| Revenue growth | (Revenue_t / Revenue_t-1) − 1 |
| Gross margin | (Revenue − materials − purchases − Δinventories) / Revenue |
| EBITDA margin | (Revenue − materials − purchases − Δinventories − employee costs − other expenses) / Revenue |
| PAT margin | Profit for the year / Revenue |
| PAT growth | (PAT_t / PAT_t-1) − 1, flagged when either year includes exceptional items |
| ROE | Profit attributable to owners / average equity attributable to owners |
| Net cash (debt) | Cash + other bank balances + current investments − borrowings |
| Debt-to-equity | Borrowings / total equity (shown, but low for all three) |
| Free cash flow | Operating cash flow − capex |
| Cash conversion | Operating cash flow / PAT |
| Receivable days | Trade receivables / Revenue × 365 |
| Inventory days | Inventories / (materials + purchases + Δinventories) × 365 |

EBITDA is built from the operating cost lines, so it automatically excludes other income, exceptional items and the share of associates/JVs. (Changed from the first draft, which worked backwards from PBT and would have wrongly included JV profits.)

Exceptional items are stored as their effect on profit: gains positive, losses negative.

Rules:
- Missing input → metric is NULL with a reason. Gaps are never filled with zero.
- Growth rates are not shown when the earlier value is negative or zero.
- All amounts are in ₹ crore, all ratios are decimals stored and shown as %.

---

## 8. Validation requirements

Run automatically by `validation.py` every time the database is built:
1. **Completeness:** every company × year × required item is present or explicitly NULL with a note.
2. **Units:** every value has `unit_as_reported`, and conversions to ₹ crore are tested.
3. **Accounting identities:** total assets = total equity and liabilities (within ₹1 crore rounding); PBT − tax = profit for the year.
4. **Restatement check:** each report also prints the previous year's figures. Where those differ from the earlier report, it's flagged in `note`.
5. **Plausibility:** margins between −50% and +60%, no negative revenue, year-on-year jumps above 50% flagged for manual review.
6. **Spot check:** at least 20 randomly chosen values re-checked by hand against the PDF page, with the result recorded in `eval/`.
7. **Second source:** revenue and PAT for all 15 company-years cross-checked against a public aggregator (Screener.in). Differences are explained, not ignored.

RAG evaluation (`eval/questions.csv`, about 25 questions):
- Types: narrative questions (for example "What risks did management highlight?"), numeric questions (must be answered from the database, not the text), and **trap questions** whose answer is not in the filings (the system must say so).
- Measured: whether the right page appears in the top 5 results, citation accuracy, refusal rate on trap questions, and unsupported claims (checked by hand).

---

## 9. Conventions

- Plain, readable Python: functions, not classes, unless a class clearly helps. Every function has a docstring that explains what it does in one line.
- One formula = one function in `metrics.py`, with a test using a hand-calculated example.
- Never hard-code an API key. Read `GEMINI_API_KEY` and `GEMINI_MODEL` from `.env`.
- Commit at the end of each milestone with a message that says what was verified.
- Citations always use the **PDF page number**, which can differ from the printed page number at the bottom of the page.

## 10. Commands

Working now:

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
python scripts/check_documents.py # Milestone 1: expect "15/15 documents passed"
pytest                            # all tests
```

Coming in later milestones:

```bash
python scripts/build_database.py  # Milestone 2–4
python scripts/build_index.py     # Milestone 5–6
python scripts/run_eval.py        # Milestone 10
streamlit run app.py
```

---

## 11. Milestones

| # | Milestone | Done when |
|---|---|---|
| 1 | Setup + companies + sources | See §12 |
| 2 | Curated dataset + validation | All checks in §8 (1–7) pass or are explained |
| 3 | Metrics in Python | Every metric tested against a hand-calculated example |
| 4 | SQLite + SQL queries | SQL results match Python results in tests |
| 5 | PDF ingestion | All 15 PDFs → chunks with correct page numbers |
| 6 | Retrieval + grounded answers | First evaluation run recorded |
| 7 | Combine numbers + text in answers | Numeric questions answered only from the database |
| 8 | Streamlit app | All 4 pages work, offline mode works without an API key |
| 9 | Analyst brief | Every number traceable to the database, every claim to a page |
| 10 | Test, evaluate, document | README, case study, screenshots, measured results, CV bullets |

## 12. Milestone 1: acceptance tests

Objective: a working project skeleton and a complete, checked list of source documents. No financial figures yet.

1. `pip install -r requirements.txt` completes on Windows and `pytest` runs.
2. `data/curated/companies.csv` has the 3 companies, and `documents.csv` lists all 15 annual reports with their official source URLs.
3. `python scripts/check_documents.py` reports **15/15** PDFs found and readable, with page counts recorded.
4. For each report, the PDF page numbers of the consolidated P&L, balance sheet and cash flow statement are recorded (45 references). The script confirms each of those pages contains the expected heading (for example "Consolidated Statement of Profit and Loss").
5. `line_items.csv` defines every item in §7 with its statement and definition.
6. Git repository initialised, first commit made, `.env` and PDFs confirmed ignored.

**Result (25 Oct 2026):**
- 15/15 PDFs found, unchanged (SHA-256) and readable. All have real text, so no OCR is needed.
- 45/45 statement pages verified for heading, a key line item and the correct year-end date. All are in ₹ crore.
- 28/28 tests pass (6 of them check the page logic on hand-written examples, 15 run on the real PDFs).
- Negative checks: the page check correctly rejected an auditor's-report page, a random page, Nerolac's *standalone* balance sheet and a report labelled with the wrong year.
- Still to do on your laptop: run `pip install -r requirements.txt`, `pytest` and the check script on Windows.

## 13. Known difficulties and how they are handled

| Difficulty | Handling |
|---|---|
| Asian Paints splits its annual report into several PDFs on its website | Solved: the BSE filing is one complete PDF per year |
| Printed page numbers ≠ PDF page numbers | Store and cite the PDF page number |
| Asian Paints (all years) and Berger (FY2023–26) put **two printed pages side by side on one PDF page**; Berger's balance sheet and P&L share one PDF page | `layout` column in `documents.csv`. In Milestone 5 the text of these pages is split into left and right halves so sentences from the two pages don't get mixed |
| The ₹ symbol comes out as a backtick (`) when text is extracted | Units are read from the column header ("in Crores"), not the symbol |
| BSE copies start with a cover letter to the exchange | Harmless; statement pages are recorded explicitly |
| The year check only confirms the year-end date appears on the page, and a later report also prints the earlier year as a comparison | The SHA-256 fingerprint ties each file to its registered year; Milestone 2 reads the current-year column explicitly |
| Different label wording across companies and years | `line_items.csv` maps each company's wording to one canonical item |
| Restated prior-year figures | Restatement check (§8.4) |
| One-off gains (Nerolac land sale) | `exceptional_items` stored separately and removed from EBITDA |
| Kansai Nerolac has a bigger industrial business | Flagged as a comparability limit on the comparison page and in the brief |
| Gemini model names and free-tier limits change | Model name in `.env`, answers cached, offline mode |
| Tables in PDFs extract as jumbled text | Embeddings are used for narrative text. Numbers come from the curated database |
| Beginner-level Python | Small files, no frameworks, every milestone explained before moving on |
