"""Turn the extractor's draft into the final dataset, reported_values.csv.

Rules:
  - FY2022 to FY2026: each year's figures come from THAT year's annual report
    ("as originally reported"), current-year column.
  - FY2021: taken from the previous-year (comparative) column of the FY2022 reports.
  - Any manual correction in corrections.csv replaces the extracted value and keeps its reason.
  - Notes in value_notes.csv (exceptional items, restatements) are attached to their rows.
"""

import pandas as pd

from finsight.config import (CORRECTIONS_CSV, EXTRACTED_CSV, FIRST_YEAR, REPORTED_VALUES_CSV,
                             VALUE_NOTES_CSV)

KEY = ["company_id", "fiscal_year", "item_code"]


def assemble(extracted: pd.DataFrame, corrections: pd.DataFrame, notes: pd.DataFrame) -> pd.DataFrame:
    """Build the final one-row-per-(company, year, item) table from the draft."""
    # Current-year values, from each year's own report.
    current = extracted.rename(columns={"current": "value_cr"}).drop(columns=["previous"])
    current["column"] = "current"

    # FY2021 values, from the comparative column of the first report we hold.
    first_reports = extracted[extracted["fiscal_year"] == FIRST_YEAR + 1]
    earliest = first_reports.rename(columns={"previous": "value_cr"}).drop(columns=["current"])
    earliest["fiscal_year"] = FIRST_YEAR
    earliest["column"] = "comparative"

    data = pd.concat([earliest, current], ignore_index=True)
    data["unit_as_reported"] = "INR crore"

    # Apply manual corrections (the reason is kept in the note).
    data["note"] = ""
    for _, fix in corrections.iterrows():
        mask = ((data["company_id"] == fix["company_id"]) & (data["fiscal_year"] == fix["fiscal_year"])
                & (data["item_code"] == fix["item_code"]))
        data.loc[mask, "value_cr"] = fix["value_cr"]
        data.loc[mask, "page"] = fix["page"]
        data.loc[mask, "method"] = "manual_correction"
        data.loc[mask, "note"] = "Correction: " + str(fix["reason"])

    # Attach explanatory notes.
    for _, n in notes.iterrows():
        mask = ((data["company_id"] == n["company_id"]) & (data["fiscal_year"] == n["fiscal_year"])
                & (data["item_code"] == n["item_code"]))
        data.loc[mask, "note"] = (data.loc[mask, "note"] + " " + n["note"]).str.strip()

    columns = KEY + ["value_cr", "unit_as_reported", "document_id", "page", "column",
                     "label_as_reported", "method", "note"]
    data["page"] = data["page"].astype("Int64")  # whole numbers, blank where there is no line
    return data[columns].sort_values(KEY).reset_index(drop=True)


def build_and_save() -> pd.DataFrame:
    """Read the draft, corrections and notes; write reported_values.csv."""
    data = assemble(pd.read_csv(EXTRACTED_CSV), pd.read_csv(CORRECTIONS_CSV), pd.read_csv(VALUE_NOTES_CSV))
    data.to_csv(REPORTED_VALUES_CSV, index=False)
    return data


def load_reported_values() -> pd.DataFrame:
    """The final dataset: one row per company, financial year and line item."""
    values = pd.read_csv(REPORTED_VALUES_CSV, keep_default_na=False, na_values=[""])
    values["page"] = values["page"].astype("Int64")
    values["note"] = values["note"].fillna("")
    return values


def wide(values: pd.DataFrame, value_column: str = "value_cr") -> pd.DataFrame:
    """Reshape to one row per (company, year) and one column per line item."""
    return values.pivot_table(index=["company_id", "fiscal_year"], columns="item_code",
                              values=value_column, aggfunc="first")
