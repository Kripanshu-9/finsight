"""Checks on the financial dataset (PROJECT_NOTES.md section 8).

Every check returns a list of Finding objects:
  FAIL - must be fixed before the data is used,
  WARN - unusual but possibly genuine; needs a human look,
  INFO - recorded for transparency (e.g. a restatement we have explained).
"""

from dataclasses import dataclass

import pandas as pd

from finsight.config import FIRST_YEAR, LAST_YEAR
from finsight.dataset import wide

TOLERANCE = 0.05     # ₹ crore; statements are printed to 2 decimals, so totals should agree exactly
SECOND_SOURCE_TOLERANCE = 1.0  # ₹ crore; Screener rounds to whole crores

NO_PAGE_METHODS = {"absent_nil", "equals_profit_before_tax"}


@dataclass
class Finding:
    check: str
    level: str        # "FAIL", "WARN" or "INFO"
    company_id: str
    fiscal_year: int
    message: str


def check_completeness(values: pd.DataFrame, line_items: pd.DataFrame, companies: list) -> list:
    """Every company x year x line item must be present with a value (no silent gaps)."""
    findings = []
    have = set(zip(values["company_id"], values["fiscal_year"], values["item_code"]))
    for company in companies:
        for year in range(FIRST_YEAR, LAST_YEAR + 1):
            for item in line_items["item_code"]:
                if (company, year, item) not in have:
                    findings.append(Finding("completeness", "FAIL", company, year, f"{item} missing"))
    for _, row in values[values["value_cr"].isna()].iterrows():
        findings.append(Finding("completeness", "FAIL", row["company_id"], row["fiscal_year"],
                                f"{row['item_code']} has no value"))
    return findings


def check_units_and_sources(values: pd.DataFrame, documents: pd.DataFrame) -> list:
    """Every value is in INR crore and points to a real page of the right report."""
    findings = []
    docs = documents.set_index("document_id")
    for _, row in values.iterrows():
        where = (row["company_id"], row["fiscal_year"])
        if row["unit_as_reported"] != "INR crore":
            findings.append(Finding("units", "FAIL", *where, f"{row['item_code']}: unit {row['unit_as_reported']}"))
        if row["document_id"] not in docs.index:
            findings.append(Finding("source", "FAIL", *where, f"{row['item_code']}: unknown document"))
            continue
        doc = docs.loc[row["document_id"]]
        expected_year = row["fiscal_year"] + (1 if row["column"] == "comparative" else 0)
        if doc["fiscal_year"] != expected_year or doc["company_id"] != row["company_id"]:
            findings.append(Finding("source", "FAIL", *where, f"{row['item_code']}: wrong source document"))
        if row["method"] in NO_PAGE_METHODS:
            continue
        if pd.isna(row["page"]) or not 1 <= int(row["page"]) <= doc["page_count"]:
            findings.append(Finding("source", "FAIL", *where, f"{row['item_code']}: missing or invalid page"))
    return findings


def identity_differences(w: pd.DataFrame) -> pd.DataFrame:
    """Accounting identities that must hold in every statement. Each column should be ~0."""
    operating_costs = (w["cost_of_materials_consumed"] + w["purchases_of_stock_in_trade"]
                       + w["change_in_inventories"] + w["employee_benefits_expense"]
                       + w["finance_costs"] + w["depreciation_amortisation"] + w["other_expenses"])
    return pd.DataFrame({
        "total assets = total equity and liabilities":
            w["total_assets"] - w["total_equity_and_liabilities"],
        "owners' equity + NCI = total equity":
            w["equity_attributable_to_owners"] + w["non_controlling_interests"] - w["total_equity"],
        "profit before tax - tax = profit for the year":
            w["profit_before_tax"] - w["tax_expense"] - w["profit_for_the_year"],
        "profit before exceptional items + exceptional items = profit before tax":
            w["profit_before_exceptional"] + w["exceptional_items"] - w["profit_before_tax"],
        "revenue + other income - expenses + share of associates/JVs + exceptional items = profit before tax":
            w["revenue_from_operations"] + w["other_income"] - operating_costs
            + w["share_of_profit_associates_jv"] + w["exceptional_items"] - w["profit_before_tax"],
    })


def check_identities(values: pd.DataFrame) -> list:
    """The statements must add up, which catches most wrongly read numbers."""
    findings = []
    diffs = identity_differences(wide(values))
    for (company, year), row in diffs.iterrows():
        for identity, diff in row.items():
            if abs(diff) > TOLERANCE:
                findings.append(Finding("identity", "FAIL", company, year, f"{identity}: off by {diff:,.2f}"))
    return findings


def restatement_differences(extracted: pd.DataFrame) -> pd.DataFrame:
    """Compare each year's figure with how the NEXT year's report prints it as a comparative."""
    original = extracted[["company_id", "fiscal_year", "item_code", "current"]]
    comparative = extracted[["company_id", "fiscal_year", "item_code", "previous"]].copy()
    comparative["fiscal_year"] -= 1
    merged = original.merge(comparative, on=["company_id", "fiscal_year", "item_code"])
    merged["difference"] = (merged["previous"] - merged["current"]).round(2)
    return merged


def check_restatements(extracted: pd.DataFrame, notes: pd.DataFrame) -> list:
    """Two independent readings of the same number (from two different reports) must agree,
    unless the later report restated it AND we have written down why."""
    findings = []
    merged = restatement_differences(extracted)
    explained = set(zip(notes["company_id"], notes["fiscal_year"], notes["item_code"]))
    for _, row in merged[merged["difference"].abs() > 0.01].iterrows():
        key = (row["company_id"], row["fiscal_year"], row["item_code"])
        message = (f"{row['item_code']}: {row['current']:,.2f} as reported, "
                   f"{row['previous']:,.2f} in next year's report")
        level = "INFO" if key in explained else "FAIL"
        findings.append(Finding("restatement", level, row["company_id"], row["fiscal_year"], message))
    return findings


def check_exceptional_items_explained(values: pd.DataFrame) -> list:
    """Every non-zero exceptional item needs a written explanation from the notes to accounts."""
    findings = []
    rows = values[(values["item_code"] == "exceptional_items") & (values["value_cr"].abs() > 0)]
    for _, row in rows.iterrows():
        level = "INFO" if str(row["note"]).strip() else "FAIL"
        findings.append(Finding("exceptional items", level, row["company_id"], row["fiscal_year"],
                                f"{row['value_cr']:,.2f}: {row['note'] or 'NO EXPLANATION'}"))
    return findings


def check_plausibility(values: pd.DataFrame) -> list:
    """Ranges that real paint companies should fall in; big jumps get a human look."""
    findings = []
    w = wide(values)
    ebitda = (w["revenue_from_operations"] - w["cost_of_materials_consumed"] - w["purchases_of_stock_in_trade"]
              - w["change_in_inventories"] - w["employee_benefits_expense"] - w["other_expenses"])
    for (company, year), row in w.iterrows():
        if row["revenue_from_operations"] <= 0 or row["total_assets"] <= 0:
            findings.append(Finding("plausibility", "FAIL", company, year, "revenue or total assets not positive"))
        margin = ebitda[(company, year)] / row["revenue_from_operations"]
        if not -0.5 <= margin <= 0.6:
            findings.append(Finding("plausibility", "FAIL", company, year, f"EBITDA margin {margin:.1%} out of range"))
    for item in ["revenue_from_operations", "profit_for_the_year", "total_assets"]:
        change = w[item].groupby(level="company_id").pct_change()
        for (company, year), pct in change.dropna().items():
            if abs(pct) > 0.5:
                exceptional = w.loc[(company, year), "exceptional_items"]
                reason = f" (exceptional items this year: {exceptional:,.2f})" if exceptional else ""
                findings.append(Finding("plausibility", "WARN", company, year,
                                        f"{item} changed {pct:+.0%} year on year{reason}"))
    return findings


def check_second_source(values: pd.DataFrame, second: pd.DataFrame) -> list:
    """Compare revenue, profit and operating cash flow with Screener.in (rounded to ₹1 crore)."""
    findings = []
    w = wide(values)
    for _, row in second.iterrows():
        key = (row["company_id"], row["fiscal_year"])
        for item in ["revenue_from_operations", "profit_for_the_year", "net_cash_from_operating_activities"]:
            ours = w.loc[key, item]
            diff = ours - row[item]
            if abs(diff) > SECOND_SOURCE_TOLERANCE:
                findings.append(Finding("second source", "FAIL", *key,
                                        f"{item}: ours {ours:,.2f} vs Screener {row[item]:,} (diff {diff:,.2f})"))
    return findings


def check_spot_check(spot: pd.DataFrame) -> list:
    """Score the hand check: values typed from the PDF must match the dataset.
    Rows not filled in yet are reported as WARN so they are not forgotten."""
    findings = []
    for _, row in spot.iterrows():
        where = (row["company_id"], row["fiscal_year"])
        typed = str(row["value_in_pdf"]).strip()
        if typed in ("", "nan"):
            findings.append(Finding("spot check", "WARN", *where, f"{row['line_item']}: not checked yet"))
            continue
        printed = parse_typed_number(typed)
        expected = row["value_cr"]
        # Capital expenditure is printed as an outflow but stored as a positive amount.
        # stored as a positive amount (capex) or as the effect on profit (exceptional items),
        # so for these two the printed sign may legitimately differ: compare sizes only.
        if printed is not None and (row["line_item"].startswith("Purchase of property")
                                    or row["line_item"] == "Exceptional items"):
            printed, expected = abs(printed), abs(expected)
        if printed is None or abs(printed - expected) > 0.005:
            findings.append(Finding("spot check", "FAIL", *where,
                                    f"{row['line_item']}: dataset {expected:,.2f}, PDF shows {typed}"))
        else:
            findings.append(Finding("spot check", "INFO", *where, f"{row['line_item']}: matches ({typed})"))
    return findings


def parse_typed_number(text: str):
    """Read a number typed by a person: '1,234.56', '(12.30)', '-12.3', '-' (nil). None if unreadable."""
    if text.strip() in {"-", "–", "—", "0"}:
        return 0.0
    try:
        negative = text.startswith("(") or text.startswith("-")
        value = float(text.strip("()- ").replace(",", ""))
        return -value if negative else value
    except ValueError:
        return None


def run_all(values, extracted, notes, line_items, documents, companies, second) -> list:
    """Run every check and return all findings."""
    return (check_completeness(values, line_items, companies)
            + check_units_and_sources(values, documents)
            + check_identities(values)
            + check_restatements(extracted, notes)
            + check_exceptional_items_explained(values)
            + check_plausibility(values)
            + check_second_source(values, second))
