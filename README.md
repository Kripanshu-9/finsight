# FinSight

**AI-powered financial research platform** comparing three listed Indian paint companies (Asian Paints, Berger Paints, Kansai Nerolac) across FY2022–FY2026.

FinSight combines:
1. **Verified numbers.** Figures from the consolidated financial statements, each stored with its source page, with metrics calculated by Python and SQL.
2. **Cited answers.** Questions about the annual reports are answered only from retrieved passages, with document and page references. It says so when the evidence isn't there.
3. **Analyst briefs.** Every number comes from the database. The AI writes only the cited commentary.

> **Status:** in development. Milestones 1–3 of 10 are complete:
> - 15 source reports verified, and 558 financial figures (3 companies × FY2021–26 × 31 line items) collected with page references.
> - Every figure passes 90 accounting-identity checks, 372 cross-report comparisons (2 restatements, both explained) and 54 second-source comparisons. A random sample of 20 was also verified by hand against the PDFs: 20/20 correct.
> - 23 financial metrics (growth, margins, ROE/ROCE, net cash, cash conversion, working-capital days), each tested against hand calculations. Comparison tables: [`eval/metrics_summary.md`](eval/metrics_summary.md).
>
> Full design: [PROJECT_NOTES.md](PROJECT_NOTES.md).

## Data sources

Official annual reports filed with BSE, FY2022–FY2026 (15 PDFs). The register with links, page counts, file fingerprints and statement page numbers is in [`data/curated/documents.csv`](data/curated/documents.csv).

The financial dataset is [`data/curated/reported_values.csv`](data/curated/reported_values.csv): one row per company, year and line item, with the source document, PDF page and wording as printed. The latest data checks are in [`eval/data_validation.md`](eval/data_validation.md).

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
python scripts/build_dataset.py     # re-reads the statements and rebuilds the dataset
python scripts/validate_data.py     # expect: 0 FAIL
python scripts/build_metrics.py     # calculates all metrics and the comparison tables
pytest                              # expect: all tests pass
```

## Project status

| Milestone | Status |
|---|---|
| 1. Setup, companies, sources | ✅ Done |
| 2. Curated dataset + validation | ✅ Done |
| 3. Financial metrics in Python | ✅ Done |
| 4. SQLite database + SQL queries | Next |
| 5–10. Retrieval, app, brief, evaluation | Planned |

Limitations, results and the case study will be documented here as each milestone is verified.
