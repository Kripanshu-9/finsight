"""Financial metrics, calculated in Python from the verified dataset.

Each metric is one small function that takes two arguments:
    cur  - this year's line items for one company (e.g. cur["revenue_from_operations"])
    prev - the previous year's line items, or None for the first year we hold (FY2021)
and returns a number. Formulas are written out in data/curated/metric_definitions.csv.

When a metric cannot be calculated sensibly (no previous year, or dividing by zero
or a negative number), the function raises NotMeaningful with the reason. The value
is then left blank WITH that reason; it is never replaced by 0.

Percentages are stored as fractions (0.183 = 18.3%). Amounts are in INR crore.
"""

import pandas as pd

DAYS_IN_YEAR = 365


class NotMeaningful(Exception):
    """Raised when a metric cannot be calculated meaningfully. The message says why."""


# ---------- Small helpers ----------

def ratio(numerator: float, denominator: float, what: str) -> float:
    """numerator / denominator, refusing to divide by zero or a negative base."""
    if denominator <= 0:
        raise NotMeaningful(f"{what} is zero or negative")
    return numerator / denominator


def growth(current: float, previous: float, what: str) -> float:
    """Year-on-year growth. Not meaningful if the earlier value is zero or negative
    (e.g. going from a loss of 10 to a profit of 20 is not '-300% growth')."""
    if previous <= 0:
        raise NotMeaningful(f"previous year's {what} is zero or negative")
    return current / previous - 1


def need_previous(prev) -> None:
    if prev is None:
        raise NotMeaningful("needs the previous year, which is not in the dataset")


def average(current: float, previous: float) -> float:
    return (current + previous) / 2


# ---------- Building blocks (also used inside other metrics) ----------

def cost_of_goods_sold(r) -> float:
    """Materials used + finished goods bought for resale + change in inventories."""
    return (r["cost_of_materials_consumed"] + r["purchases_of_stock_in_trade"]
            + r["change_in_inventories"])


def ebitda(cur, prev=None) -> float:
    """Revenue minus all operating costs. Excludes other income, depreciation,
    interest, share of associates, exceptional items and tax."""
    return (cur["revenue_from_operations"] - cost_of_goods_sold(cur)
            - cur["employee_benefits_expense"] - cur["other_expenses"])


def total_debt(cur, prev=None) -> float:
    return cur["borrowings_non_current"] + cur["borrowings_current"]


def cash_and_investments(cur, prev=None) -> float:
    return cur["cash_and_cash_equivalents"] + cur["other_bank_balances"] + cur["current_investments"]


def capital_employed(r) -> float:
    """Long-term money in the business: shareholders' equity plus borrowings."""
    return r["total_equity"] + total_debt(r)


# ---------- Growth ----------

def revenue_growth(cur, prev):
    need_previous(prev)
    return growth(cur["revenue_from_operations"], prev["revenue_from_operations"], "revenue")


def ebitda_growth(cur, prev):
    need_previous(prev)
    return growth(ebitda(cur), ebitda(prev), "EBITDA")


def pat_growth(cur, prev):
    need_previous(prev)
    return growth(cur["profit_for_the_year"], prev["profit_for_the_year"], "profit")


def underlying_pbt_growth(cur, prev):
    need_previous(prev)
    return growth(cur["profit_before_exceptional"], prev["profit_before_exceptional"],
                  "profit before exceptional items")


# ---------- Profitability ----------

def gross_margin(cur, prev=None):
    revenue = cur["revenue_from_operations"]
    return ratio(revenue - cost_of_goods_sold(cur), revenue, "revenue")


def ebitda_margin(cur, prev=None):
    return ratio(ebitda(cur), cur["revenue_from_operations"], "revenue")


def pat_margin(cur, prev=None):
    return ratio(cur["profit_for_the_year"], cur["revenue_from_operations"], "revenue")


def underlying_pbt_margin(cur, prev=None):
    return ratio(cur["profit_before_exceptional"], cur["revenue_from_operations"], "revenue")


# ---------- Returns ----------

def roe(cur, prev):
    """Owners' profit / average owners' equity over the year."""
    need_previous(prev)
    equity = average(cur["equity_attributable_to_owners"], prev["equity_attributable_to_owners"])
    return ratio(cur["profit_attributable_to_owners"], equity, "average equity")


def roce(cur, prev):
    """EBIT / average capital employed. EBIT = profit before exceptional items and tax
    + finance costs, so it includes other income (e.g. treasury income on cash)."""
    need_previous(prev)
    ebit = cur["profit_before_exceptional"] + cur["finance_costs"]
    return ratio(ebit, average(capital_employed(cur), capital_employed(prev)), "average capital employed")


# ---------- Balance sheet ----------

def net_cash(cur, prev=None):
    return cash_and_investments(cur) - total_debt(cur)


def debt_to_equity(cur, prev=None):
    return ratio(total_debt(cur), cur["total_equity"], "total equity")


# ---------- Cash flow ----------

def free_cash_flow(cur, prev=None):
    return cur["net_cash_from_operating_activities"] - cur["capital_expenditure"]


def capex_to_revenue(cur, prev=None):
    return ratio(cur["capital_expenditure"], cur["revenue_from_operations"], "revenue")


def cash_conversion_pat(cur, prev=None):
    return ratio(cur["net_cash_from_operating_activities"], cur["profit_for_the_year"], "profit")


def cash_conversion_ebitda(cur, prev=None):
    return ratio(cur["net_cash_from_operating_activities"], ebitda(cur), "EBITDA")


# ---------- Working capital (year-end balances) ----------

def receivable_days(cur, prev=None):
    return ratio(cur["trade_receivables"], cur["revenue_from_operations"], "revenue") * DAYS_IN_YEAR


def inventory_days(cur, prev=None):
    return ratio(cur["inventories"], cost_of_goods_sold(cur), "cost of goods sold") * DAYS_IN_YEAR


def payable_days(cur, prev=None):
    return ratio(cur["trade_payables"], cost_of_goods_sold(cur), "cost of goods sold") * DAYS_IN_YEAR


def cash_conversion_cycle(cur, prev=None):
    return receivable_days(cur) + inventory_days(cur) - payable_days(cur)


# Every metric, in display order. The keys must match metric_definitions.csv.
METRICS = {
    "revenue_growth": revenue_growth,
    "ebitda_growth": ebitda_growth,
    "pat_growth": pat_growth,
    "underlying_pbt_growth": underlying_pbt_growth,
    "gross_margin": gross_margin,
    "ebitda": ebitda,
    "ebitda_margin": ebitda_margin,
    "pat_margin": pat_margin,
    "underlying_pbt_margin": underlying_pbt_margin,
    "roe": roe,
    "roce": roce,
    "total_debt": total_debt,
    "cash_and_investments": cash_and_investments,
    "net_cash": net_cash,
    "debt_to_equity": debt_to_equity,
    "free_cash_flow": free_cash_flow,
    "capex_to_revenue": capex_to_revenue,
    "cash_conversion_pat": cash_conversion_pat,
    "cash_conversion_ebitda": cash_conversion_ebitda,
    "receivable_days": receivable_days,
    "inventory_days": inventory_days,
    "payable_days": payable_days,
    "cash_conversion_cycle": cash_conversion_cycle,
}

# Reported-profit metrics that are distorted when exceptional items exist. Growth metrics
# look at both years, because a one-off in the previous year distorts growth too.
AFFECTED_BY_EXCEPTIONAL = {"pat_growth", "pat_margin", "roe", "cash_conversion_pat"}
LOOKS_AT_PREVIOUS_YEAR = {"pat_growth"}


def exceptional_flag(metric: str, cur, prev) -> str:
    """A warning when a reported-profit metric includes one-off items."""
    if metric not in AFFECTED_BY_EXCEPTIONAL:
        return ""
    parts = []
    if cur["exceptional_items"] != 0:
        parts.append(f"this year includes exceptional items of {cur['exceptional_items']:,.2f} cr")
    if metric in LOOKS_AT_PREVIOUS_YEAR and prev is not None and prev["exceptional_items"] != 0:
        parts.append(f"previous year includes exceptional items of {prev['exceptional_items']:,.2f} cr")
    return "; ".join(parts)


def compute_metrics(wide_values: pd.DataFrame) -> pd.DataFrame:
    """Calculate every metric for every company and year.

    wide_values: one row per (company_id, fiscal_year), one column per line item
                 (see dataset.wide()).
    Returns one row per (company, year, metric) with value, null_reason and flag.
    """
    rows = []
    for company, years in wide_values.groupby(level="company_id"):
        years = years.droplevel("company_id").sort_index()
        previous = None
        for year, current in years.iterrows():
            # Only use the row as "previous" if it really is the year before.
            prev = previous if previous is not None and previous.name == year - 1 else None
            for code, function in METRICS.items():
                try:
                    value, reason = float(function(current, prev)), ""
                except NotMeaningful as why:
                    value, reason = None, str(why)
                rows.append(dict(company_id=company, fiscal_year=int(year), metric_code=code,
                                 value=value, null_reason=reason,
                                 flag=exceptional_flag(code, current, prev)))
            previous = current
    return pd.DataFrame(rows)
