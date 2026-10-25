"""Tests for the document register and the statement-page checks."""

import pytest

from finsight.config import REPORTS_DIR
from finsight.documents import (
    check_document,
    check_statement_text,
    load_companies,
    load_documents,
)

YEARS = [2022, 2023, 2024, 2025, 2026]


# ---------- The register itself ----------

def test_register_has_every_company_and_year():
    docs = load_documents()
    companies = load_companies()["company_id"].tolist()
    assert len(companies) == 3
    assert len(docs) == 15
    for company in companies:
        years = sorted(docs.loc[docs["company_id"] == company, "fiscal_year"])
        assert years == YEARS, f"{company} is missing a year"


def test_document_ids_and_files_are_unique():
    docs = load_documents()
    assert docs["document_id"].is_unique
    assert docs["file_name"].is_unique


def test_every_document_has_source_url_and_unit():
    docs = load_documents()
    assert docs["source_url"].str.startswith("https://").all()
    assert (docs["unit_as_reported"] == "INR crore").all()


def test_statement_pages_are_inside_each_pdf():
    docs = load_documents()
    for column in ["bs_page", "pl_page", "cf_page"]:
        assert (docs[column] >= 1).all()
        assert (docs[column] <= docs["page_count"]).all()


# ---------- The page check, on small hand-written examples ----------

def test_accepts_standard_wording():
    text = "Consolidated Balance Sheet as at 31st March, 2026 ... Total Assets 9,131.64"
    assert check_statement_text(text, "bs", 2026) == []


def test_accepts_berger_2022_wording():
    text = ("STATEMENT OF CONSOLIDATED PROFIT AND LOSS FOR THE YEAR ENDED MARCH 31, 2022 "
            "Revenue from operations 8,761.78")
    assert check_statement_text(text, "pl", 2022) == []


def test_accepts_superscript_date_and_cash_flow_variant():
    # PDFs often split the superscript "st" onto its own line.
    text = "Consolidated Statement of Cash Flow\nfor the year ended 31\nst\n March, 2026 Operating Activities"
    assert check_statement_text(text, "cf", 2026) == []


def test_rejects_standalone_statement():
    text = "Standalone Balance Sheet as at 31st March, 2024 Total assets 100"
    assert any("heading" in p for p in check_statement_text(text, "bs", 2024))


def test_rejects_wrong_year():
    text = "Consolidated Balance Sheet as at 31st March, 2024 Total assets 100"
    assert any("FY2025" in p for p in check_statement_text(text, "bs", 2025))


def test_rejects_page_that_only_mentions_the_statement():
    # e.g. the auditor's report names the statement but has no figures.
    text = "We have audited the Consolidated Balance Sheet as at 31st March, 2026 and ..."
    assert any("line item" in p for p in check_statement_text(text, "bs", 2026))


# ---------- The real PDFs (skipped if they have not been downloaded) ----------

def _pdfs_available() -> bool:
    return all((REPORTS_DIR / name).exists() for name in load_documents()["file_name"])


@pytest.mark.skipif(not _pdfs_available(), reason="annual report PDFs not in data/reports")
@pytest.mark.parametrize("document_id", load_documents()["document_id"].tolist())
def test_real_pdf_passes_all_checks(document_id):
    docs = load_documents()
    row = docs.loc[docs["document_id"] == document_id].iloc[0]
    assert check_document(row) == []
