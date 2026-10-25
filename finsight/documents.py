"""Load the list of annual reports and check that each PDF is present and correct.

For every report we check:
  1. the PDF file exists and opens,
  2. it is exactly the file we registered (same SHA-256 fingerprint and page count),
  3. the pages we recorded for the three consolidated statements really contain
     those statements, for the right financial year.
"""

import hashlib
import re

import pandas as pd
import pymupdf

from finsight.config import COMPANIES_CSV, DOCUMENTS_CSV, LINE_ITEMS_CSV, REPORTS_DIR

# For each statement: (pattern for the heading, pattern for a line item that must
# also be on the page). The second pattern stops us from accepting a page that only
# *mentions* the statement, such as the auditor's report or the table of contents.
STATEMENT_CHECKS = {
    "bs": (
        r"consolidated balance sheet",
        r"total assets",
    ),
    "pl": (
        # Berger's FY2022 report words it "Statement of Consolidated Profit and Loss".
        r"consolidated statement of profit (and|&) loss|statement of consolidated profit (and|&) loss",
        r"revenue from operations",
    ),
    "cf": (
        # Wording varies: "Cash Flow Statement", "Statement of Cash Flows", "Statement of Cash Flow".
        r"consolidated (statement of cash flows?|cash flow statement)",
        r"operating activities",
    ),
}

STATEMENT_NAMES = {"bs": "Balance sheet", "pl": "Profit and loss", "cf": "Cash flow"}


def load_companies() -> pd.DataFrame:
    """Read the list of companies."""
    return pd.read_csv(COMPANIES_CSV)


def load_documents() -> pd.DataFrame:
    """Read the register of annual reports (one row per PDF)."""
    return pd.read_csv(DOCUMENTS_CSV)


def load_line_items() -> pd.DataFrame:
    """Read the dictionary of financial line items we will collect."""
    return pd.read_csv(LINE_ITEMS_CSV)


def normalise(text: str) -> str:
    """Lower-case the text and squash all runs of spaces and line breaks into one space."""
    return re.sub(r"\s+", " ", text).lower()


def year_end_pattern(fiscal_year: int) -> str:
    """Regex for the year-end date, e.g. '31st March, 2026', 'March 31, 2026' or '31.03.2026'."""
    return rf"31\s*(st)?\s+march,?\s+{fiscal_year}|march\s+31,?\s+{fiscal_year}|31\.03\.{fiscal_year}"


def check_statement_text(text: str, statement: str, fiscal_year: int) -> list[str]:
    """Check one page's text for a statement. Returns a list of problems (empty = OK)."""
    heading_pattern, line_item_pattern = STATEMENT_CHECKS[statement]
    page = normalise(text)
    name = STATEMENT_NAMES[statement]
    problems = []
    if not re.search(heading_pattern, page):
        problems.append(f"{name}: consolidated heading not found")
    if not re.search(line_item_pattern, page):
        problems.append(f"{name}: expected line item not found")
    if not re.search(year_end_pattern(fiscal_year), page):
        problems.append(f"{name}: year-end date for FY{fiscal_year} not found")
    return problems


def file_sha256(path) -> str:
    """Fingerprint of a file. Any change to the file changes this value."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_document(row: pd.Series, reports_dir=REPORTS_DIR) -> list[str]:
    """Run every check for one registered report. Returns a list of problems (empty = OK)."""
    path = reports_dir / row["file_name"]
    if not path.exists():
        return [f"file not found: {path}"]

    problems = []
    if file_sha256(path) != row["sha256"]:
        problems.append("file differs from the registered version (SHA-256 mismatch)")

    doc = pymupdf.open(path)
    if doc.page_count != row["page_count"]:
        problems.append(f"page count is {doc.page_count}, expected {row['page_count']}")

    for statement in ["bs", "pl", "cf"]:
        page_number = int(row[f"{statement}_page"])  # PDF page number, starting at 1
        if not 1 <= page_number <= doc.page_count:
            problems.append(f"{STATEMENT_NAMES[statement]}: page {page_number} is outside the PDF")
            continue
        text = doc[page_number - 1].get_text()  # pymupdf counts pages from 0
        problems += check_statement_text(text, statement, int(row["fiscal_year"]))

    doc.close()
    return problems
