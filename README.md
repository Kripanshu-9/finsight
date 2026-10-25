# FinSight

**AI-powered financial research platform** comparing three listed Indian paint companies (Asian Paints, Berger Paints, Kansai Nerolac) across FY2022–FY2026.

FinSight combines:
1. **Verified numbers.** Figures from the consolidated financial statements, each stored with its source page, with metrics calculated by Python and SQL.
2. **Cited answers.** Questions about the annual reports are answered only from retrieved passages, with document and page references. It says so when the evidence isn't there.
3. **Analyst briefs.** Every number comes from the database. The AI writes only the cited commentary.

> **Status:** in development. Milestone 1 of 10 is complete: all 15 source reports are registered and verified, and all 45 financial-statement pages are located and checked.
> Full design: [PROJECT_NOTES.md](PROJECT_NOTES.md).

## Data sources

Official annual reports filed with BSE, FY2022–FY2026 (15 PDFs). The register with links, page counts, file fingerprints and statement page numbers is in [`data/curated/documents.csv`](data/curated/documents.csv).

## Setup (so far)

Requires Python 3.12 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Download the PDFs as described in [`data/reports/README.md`](data/reports/README.md), then:

```bash
python scripts/check_documents.py   # expect: 15/15 documents passed; 45/45 statement pages verified
pytest                              # expect: all tests pass
```

## Project status

| Milestone | Status |
|---|---|
| 1. Setup, companies, sources | ✅ Done |
| 2. Curated dataset + validation | Next |
| 3–10. Metrics, SQL, retrieval, app, brief, evaluation | Planned |

Limitations, results and the case study will be documented here as each milestone is verified.
