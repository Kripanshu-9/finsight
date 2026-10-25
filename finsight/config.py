"""All file locations used by the project, kept in one place."""

from pathlib import Path

# The project root is the folder that contains this "finsight" package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"      # annual report PDFs (not committed to Git)
CURATED_DIR = DATA_DIR / "curated"      # hand-checked CSV files (committed)
PROCESSED_DIR = DATA_DIR / "processed"  # database and search index (rebuilt by scripts)

COMPANIES_CSV = CURATED_DIR / "companies.csv"
DOCUMENTS_CSV = CURATED_DIR / "documents.csv"
LINE_ITEMS_CSV = CURATED_DIR / "line_items.csv"
EXTRACTED_CSV = CURATED_DIR / "extracted_values.csv"      # draft output of the extractor
CORRECTIONS_CSV = CURATED_DIR / "corrections.csv"          # manual fixes, each with a reason
VALUE_NOTES_CSV = CURATED_DIR / "value_notes.csv"          # explanations (exceptional items, restatements)
REPORTED_VALUES_CSV = CURATED_DIR / "reported_values.csv"  # final dataset used by the app
SECOND_SOURCE_CSV = CURATED_DIR / "second_source_screener.csv"

EVAL_DIR = PROJECT_ROOT / "eval"

FIRST_YEAR = 2021  # FY2021 comes from the comparative column of the FY2022 reports
LAST_YEAR = 2026
