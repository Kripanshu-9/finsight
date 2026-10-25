"""Tests for assembling the dataset and for the validation checks."""

import pandas as pd

from finsight.config import EXTRACTED_CSV, SECOND_SOURCE_CSV, VALUE_NOTES_CSV
from finsight.dataset import assemble, load_reported_values
from finsight.documents import load_companies, load_documents, load_line_items
from finsight.validation import (check_exceptional_items_explained, check_identities, check_restatements,
                                 check_second_source, check_spot_check, run_all)


# ---------- Assembling ----------

def tiny_extract():
    return pd.DataFrame([
        dict(company_id="X", fiscal_year=2022, item_code="revenue_from_operations", document_id="X_FY2022_AR",
             current=110.0, previous=100.0, page=5, label_as_reported="Revenue", method="matched"),
        dict(company_id="X", fiscal_year=2023, item_code="revenue_from_operations", document_id="X_FY2023_AR",
             current=121.0, previous=110.0, page=7, label_as_reported="Revenue", method="matched"),
    ])


def test_fy2021_comes_from_comparative_column():
    data = assemble(tiny_extract(), pd.DataFrame(columns=["company_id", "fiscal_year", "item_code",
                                                          "value_cr", "page", "reason"]),
                    pd.DataFrame(columns=["company_id", "fiscal_year", "item_code", "note"]))
    fy2021 = data[data["fiscal_year"] == 2021].iloc[0]
    assert fy2021["value_cr"] == 100.0
    assert fy2021["column"] == "comparative"
    assert fy2021["document_id"] == "X_FY2022_AR"
    assert len(data) == 3


def test_correction_replaces_value_and_keeps_reason():
    corrections = pd.DataFrame([dict(company_id="X", fiscal_year=2023, item_code="revenue_from_operations",
                                     value_cr=120.5, page=8, reason="misread digit")])
    data = assemble(tiny_extract(), corrections, pd.DataFrame(columns=["company_id", "fiscal_year",
                                                                       "item_code", "note"]))
    row = data[data["fiscal_year"] == 2023].iloc[0]
    assert row["value_cr"] == 120.5 and row["method"] == "manual_correction"
    assert "misread digit" in row["note"]


# ---------- The real dataset ----------

def test_dataset_shape_and_keys():
    values = load_reported_values()
    assert len(values) == 3 * 6 * len(load_line_items())
    assert not values.duplicated(["company_id", "fiscal_year", "item_code"]).any()


def all_findings():
    return run_all(load_reported_values(), pd.read_csv(EXTRACTED_CSV), pd.read_csv(VALUE_NOTES_CSV),
                   load_line_items(), load_documents(), load_companies()["company_id"].tolist(),
                   pd.read_csv(SECOND_SOURCE_CSV))


def test_real_dataset_has_no_failures():
    failures = [f for f in all_findings() if f.level == "FAIL"]
    assert failures == [], failures[:5]


# ---------- Each check really catches the problem it is meant to catch ----------

def test_identity_check_catches_a_misread_number():
    values = load_reported_values()
    mask = ((values["company_id"] == "BERGEPAINT") & (values["fiscal_year"] == 2025)
            & (values["item_code"] == "other_expenses"))
    values.loc[mask, "value_cr"] = 2111.90  # true value 2,111.99: a single wrong digit
    failures = check_identities(values)
    assert any(f.company_id == "BERGEPAINT" and f.fiscal_year == 2025 for f in failures)


def test_unexplained_restatement_fails_but_explained_one_passes():
    extracted = pd.read_csv(EXTRACTED_CSV)
    notes = pd.read_csv(VALUE_NOTES_CSV)
    levels = {f.level for f in check_restatements(extracted, notes)}
    assert levels == {"INFO"}
    no_notes = notes.iloc[0:0]
    assert {f.level for f in check_restatements(extracted, no_notes)} == {"FAIL"}


def test_exceptional_item_without_note_fails():
    values = load_reported_values()
    values["note"] = ""
    assert all(f.level == "FAIL" for f in check_exceptional_items_explained(values))


def test_second_source_catches_large_difference():
    second = pd.read_csv(SECOND_SOURCE_CSV)
    second.loc[0, "revenue_from_operations"] += 50
    assert len(check_second_source(load_reported_values(), second)) == 1


def test_spot_check_scoring():
    spot = pd.DataFrame([
        dict(company_id="A", fiscal_year=2025, line_item="Revenue from operations", value_cr=1234.56,
             value_in_pdf="1,234.56"),
        dict(company_id="A", fiscal_year=2025, line_item="Exceptional items", value_cr=-363.10,
             value_in_pdf="363.10"),          # printed positive, stored as effect on profit
        dict(company_id="A", fiscal_year=2025, line_item="Other expenses", value_cr=100.0,
             value_in_pdf="(100.00)"),        # wrong sign: must fail
        dict(company_id="A", fiscal_year=2024, line_item="Exceptional items", value_cr=0.0,
             value_in_pdf="-"),               # dash = nil
        dict(company_id="A", fiscal_year=2025, line_item="Inventories", value_cr=5.0, value_in_pdf=""),
    ])
    levels = [f.level for f in check_spot_check(spot)]
    assert levels == ["INFO", "INFO", "FAIL", "INFO", "WARN"]
