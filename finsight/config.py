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
