"""Tests for the financial metrics.

Three kinds of test:
  1. A small made-up company with round numbers, where every expected answer was
     worked out by hand (the working is in the comments).
  2. Real figures checked by hand from a PDF page, and against Asian Paints' own
     printed EBITDA line.
  3. Awkward cases: first year, negative base, zero revenue, exceptional items.
"""

import pandas as pd
import pytest

from finsight.config import CURATED_DIR
from finsight.dataset import load_reported_values, wide
from finsight.metrics import METRICS, NotMeaningful, compute_metrics, ebitda, growth, ratio

# ---------- 1. A made-up company, calculated by hand ----------

PREVIOUS = pd.Series(dict(
    revenue_from_operations=1000, other_income=20, cost_of_materials_consumed=500,
    purchases_of_stock_in_trade=100, change_in_inventories=0, employee_benefits_expense=100,
    other_expenses=100, depreciation_amortisation=30, finance_costs=10,
    share_of_profit_associates_jv=0, exceptional_items=0,
    profit_before_exceptional=200, profit_before_tax=200, tax_expense=50, profit_for_the_year=150,
    profit_attributable_to_owners=145, equity_attributable_to_owners=900, total_equity=950,
    borrowings_non_current=30, borrowings_current=20,
), name=2024)

CURRENT = pd.Series(dict(
    revenue_from_operations=1200, other_income=30, cost_of_materials_consumed=600,
    purchases_of_stock_in_trade=120, change_in_inventories=-20,   # inventory rose by 20
    employee_benefits_expense=110, other_expenses=130, depreciation_amortisation=40,
    finance_costs=10, share_of_profit_associates_jv=0, exceptional_items=0,
    profit_before_exceptional=240, profit_before_tax=240, tax_expense=60, profit_for_the_year=180,
    profit_attributable_to_owners=170, equity_attributable_to_owners=1100, total_equity=1150,
    borrowings_non_current=20, borrowings_current=30,
    cash_and_cash_equivalents=50, other_bank_balances=30, current_investments=120,
    net_cash_from_operating_activities=216, capital_expenditure=66,
    trade_receivables=120, inventories=140, trade_payables=70,
), name=2025)

# Hand working:
#   cost of goods sold = 600 + 120 - 20 = 700
#   EBITDA = 1200 - 700 - 110 - 130 = 260          (previous: 1000 - 600 - 100 - 100 = 200)
#   EBIT = profit before exceptional items 240 + finance costs 10 = 250
#   capital employed: previous 950 + 50 = 1000, current 1150 + 50 = 1200, average 1100
HAND_ANSWERS = {
    "revenue_growth": 0.20,                    # 1200 / 1000 - 1
    "ebitda_growth": 0.30,                     # 260 / 200 - 1
    "pat_growth": 0.20,                        # 180 / 150 - 1
    "underlying_pbt_growth": 0.20,             # 240 / 200 - 1
    "gross_margin": 500 / 1200,                # (1200 - 700) / 1200 = 41.67%
    "ebitda": 260,
    "ebitda_margin": 260 / 1200,               # 21.67%
    "pat_margin": 0.15,                        # 180 / 1200
    "underlying_pbt_margin": 0.20,             # 240 / 1200
    "roe": 0.17,                               # 170 / ((1100 + 900) / 2) = 170 / 1000
    "roce": 250 / 1100,                        # 22.73%
    "total_debt": 50,                          # 20 + 30
    "cash_and_investments": 200,               # 50 + 30 + 120
    "net_cash": 150,                           # 200 - 50
    "debt_to_equity": 50 / 1150,               # 0.043x
    "free_cash_flow": 150,                     # 216 - 66
    "capex_to_revenue": 0.055,                 # 66 / 1200
    "cash_conversion_pat": 1.2,                # 216 / 180
    "cash_conversion_ebitda": 216 / 260,       # 0.83x
    "receivable_days": 36.5,                   # 120 / 1200 x 365
    "inventory_days": 73.0,                    # 140 / 700 x 365
    "payable_days": 36.5,                      # 70 / 700 x 365
    "cash_conversion_cycle": 73.0,             # 36.5 + 73 - 36.5
}


@pytest.mark.parametrize("metric", list(HAND_ANSWERS))
def test_metric_matches_hand_calculation(metric):
    assert METRICS[metric](CURRENT, PREVIOUS) == pytest.approx(HAND_ANSWERS[metric])


def test_every_metric_has_a_hand_check_and_a_definition():
    definitions = pd.read_csv(CURATED_DIR / "metric_definitions.csv")
    assert set(HAND_ANSWERS) == set(METRICS) == set(definitions["metric_code"])


# ---------- 2. Real figures ----------

def real(company, year):
    return wide(load_reported_values()).loc[(company, year)]


def test_berger_fy2025_ebitda_by_hand_from_pdf_page_205():
    # From berger_FY2025.pdf, PDF page 205 (right half), FY2025 column:
    # revenue 11,544.71; materials 5,874.69; stock purchases 1,021.65;
    # change in inventories (134.41); employee 814.70; other expenses 2,111.99
    # EBITDA = 11,544.71 - (5,874.69 + 1,021.65 - 134.41) - 814.70 - 2,111.99 = 1,856.09
    assert ebitda(real("BERGEPAINT", 2025)) == pytest.approx(1856.09, abs=0.005)
    assert METRICS["ebitda_margin"](real("BERGEPAINT", 2025)) == pytest.approx(0.160774, abs=1e-6)


# Asian Paints prints its own EBITDA line in the P&L. Its definition includes other income,
# ours does not, so: our EBITDA + other income must equal the printed figure.
ASIAN_PAINTS_PRINTED_EBITDA = {
    # year: (printed EBITDA, report and PDF page)
    2021: (5158.65, "FY2022 report p151, previous-year column"),
    2022: (5183.62, "FY2022 report p151"),
    2023: (6646.32, "FY2023 report p191"),
    2024: (8272.94, "FY2024 report p210"),
    2025: (6578.82, "FY2025 report p224"),
    2026: (7419.72, "FY2026 report p234"),
}


@pytest.mark.parametrize("year", list(ASIAN_PAINTS_PRINTED_EBITDA))
def test_ebitda_agrees_with_asian_paints_printed_line(year):
    r = real("ASIANPAINT", year)
    printed, _source = ASIAN_PAINTS_PRINTED_EBITDA[year]
    assert ebitda(r) + r["other_income"] == pytest.approx(printed, abs=0.01)


# ---------- 3. Awkward cases ----------

def test_growth_from_a_loss_is_not_meaningful():
    with pytest.raises(NotMeaningful, match="zero or negative"):
        growth(20, -10, "profit")


def test_dividing_by_zero_revenue_is_not_meaningful():
    with pytest.raises(NotMeaningful):
        ratio(5, 0, "revenue")


def test_first_year_growth_is_blank_with_a_reason():
    table = compute_metrics(pd.DataFrame([CURRENT], index=pd.MultiIndex.from_tuples(
        [("X", 2025)], names=["company_id", "fiscal_year"])))
    row = table[table["metric_code"] == "revenue_growth"].iloc[0]
    assert pd.isna(row["value"]) and "previous year" in row["null_reason"]


def test_gap_in_years_is_not_treated_as_previous_year():
    two_years = pd.DataFrame([PREVIOUS, CURRENT])
    two_years.index = pd.MultiIndex.from_tuples([("X", 2022), ("X", 2025)], names=["company_id", "fiscal_year"])
    table = compute_metrics(two_years)
    row = table[(table["fiscal_year"] == 2025) & (table["metric_code"] == "revenue_growth")].iloc[0]
    assert pd.isna(row["value"])


def test_exceptional_items_are_flagged_this_year_and_in_growth_next_year():
    with_gain = PREVIOUS.copy()
    with_gain["exceptional_items"] = 50
    two_years = pd.DataFrame([with_gain, CURRENT])
    two_years.index = pd.MultiIndex.from_tuples([("X", 2024), ("X", 2025)], names=["company_id", "fiscal_year"])
    t = compute_metrics(two_years).set_index(["fiscal_year", "metric_code"])["flag"]
    assert "this year" in t[(2024, "pat_margin")]
    assert "previous year" in t[(2025, "pat_growth")]   # growth distorted by last year's one-off
    assert t[(2025, "pat_margin")] == ""                 # this year itself is clean
    assert t[(2024, "ebitda_margin")] == ""              # underlying metrics never flagged


# ---------- The real dataset as a whole ----------

def test_real_metrics_blanks_are_only_where_expected():
    table = compute_metrics(wide(load_reported_values()))
    blanks = table[table["value"].isna()]
    assert (blanks["null_reason"] != "").all()
    assert set(blanks["fiscal_year"]) == {2021}   # only metrics that need FY2020
    assert len(table) == 3 * 6 * len(METRICS)


def test_nerolac_land_sale_years_are_flagged():
    table = compute_metrics(wide(load_reported_values())).set_index(
        ["company_id", "fiscal_year", "metric_code"])["flag"]
    assert "661.25" in table[("KANSAINER", 2024, "pat_margin")]
    assert "629.51" in table[("KANSAINER", 2025, "roe")]
