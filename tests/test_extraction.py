"""Tests for reading numbers and labels from statement pages."""

import pandas as pd
import pytest

from finsight.config import EXTRACTED_CSV, REPORTS_DIR
from finsight.documents import load_documents
from finsight.extraction import Row, add_sections, clean_label, extract_document, find_row, parse_number


# ---------- Reading numbers ----------

@pytest.mark.parametrize("text, expected", [
    ("1,234.56", 1234.56),
    ("(1,234.56)", -1234.56),     # brackets mean negative in financial statements
    ("4132.22", 4132.22),         # Nerolac prints some numbers without commas
    ("-", 0.0),                   # a dash means nil
    ("—", 0.0),
    ("0.00", 0.0),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


# ---------- Cleaning labels ----------

@pytest.mark.parametrize("raw, expected", [
    ("Inventories.......................................", "inventories"),          # leader dots
    ("(a) Borrowings 23", "borrowings"),                                               # list marker + note no.
    ("-Equity holders of the parent", "equity holders of the parent"),                # leading dash
    ("Bank Balances other than Cash and Cash Equivalents........ 13",
     "bank balances other than cash and cash equivalents"),
    ("Other Intangible assets 7(a)", "other intangible assets"),
    ("ii) Total outstanding dues of micro enterprises", "total outstanding dues of micro enterprises"),
])
def test_clean_label(raw, expected):
    assert clean_label(raw) == expected


# ---------- Finding rows ----------

def make_rows(spec):
    """spec: list of (label, numbers) -> Row objects with sections tagged."""
    return add_sections([Row(1, clean_label(label), label, numbers, "") for label, numbers in spec])


def test_section_decides_which_borrowings_row():
    rows = make_rows([
        ("Non-current liabilities", []),
        ("Borrowings", ["10.00", "20.00"]),
        ("Current liabilities", []),
        ("Borrowings", ["30.00", "40.00"]),
    ])
    assert find_row(rows, r"^borrowings", section="non_current_liabilities")[2] == (10.0, 20.0)
    assert find_row(rows, r"^borrowings", section="current_liabilities")[2] == (30.0, 40.0)


def test_wrapped_label_takes_numbers_from_a_later_line():
    rows = make_rows([
        ("Purchase of Property, Plant and Equipment and Other", []),
        ("(Including Adjustments on Account of Capital Work-", []),
        ("Creditors and Capital Advances)", ["(219.01)", "(103.79)"]),
    ])
    assert find_row(rows, r"^purchase of property", wraps=True)[2] == (-219.01, -103.79)


def test_heading_without_numbers_is_not_matched_unless_wrapping():
    rows = make_rows([("REVENUE FROM OPERATIONS", []), ("Revenue from Sale of Products", ["100.00", "90.00"])])
    assert find_row(rows, r"^revenue from operations") is None


def test_last_two_numbers_ignore_stray_dash():
    rows = make_rows([("Owners of the Company", ["-", "4,325.35", "3,667.23"])])
    assert find_row(rows, r"owners of the company")[2] == (4325.35, 3667.23)


# ---------- The real reports (skipped if the PDFs are not downloaded) ----------

def _pdfs_available() -> bool:
    return all((REPORTS_DIR / name).exists() for name in load_documents()["file_name"])


needs_pdfs = pytest.mark.skipif(not _pdfs_available(), reason="annual report PDFs not in data/reports")


@needs_pdfs
def test_two_pages_per_sheet_are_read_separately():
    """Berger FY2025 has the balance sheet (left) and P&L (right) on one PDF page."""
    docs = load_documents().set_index("document_id")
    doc = docs.loc["BERGEPAINT_FY2025_AR"]
    values = {v["item_code"]: v for v in extract_document(REPORTS_DIR / doc["file_name"],
                                                          doc["bs_page"], doc["pl_page"], doc["cf_page"])}
    assert values["total_assets"]["current"] == 9131.64             # left half
    assert values["revenue_from_operations"]["current"] == 11544.71  # right half
    assert values["profit_for_the_year"]["previous"] == 1169.82


@needs_pdfs
def test_extraction_reproduces_committed_draft():
    """Re-running the extractor on the PDFs gives exactly the committed draft CSV."""
    committed = pd.read_csv(EXTRACTED_CSV)
    docs = load_documents()
    for _, doc in docs.iterrows():
        fresh = pd.DataFrame(extract_document(REPORTS_DIR / doc["file_name"],
                                              doc["bs_page"], doc["pl_page"], doc["cf_page"]))
        saved = committed[committed["document_id"] == doc["document_id"]]
        merged = saved.merge(fresh, on="item_code", suffixes=("_saved", "_fresh"))
        assert len(merged) == len(saved) == len(fresh), doc["document_id"]
        assert (merged["current_saved"] - merged["current_fresh"]).abs().max() < 1e-9
        assert (merged["previous_saved"] - merged["previous_fresh"]).abs().max() < 1e-9
