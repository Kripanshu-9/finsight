"""Tests for the line-item dictionary."""

from finsight.documents import load_line_items

# Items the metrics in PROJECT_NOTES.md section 7 depend on.
REQUIRED_ITEMS = {
    "revenue_from_operations", "other_income", "cost_of_materials_consumed",
    "purchases_of_stock_in_trade", "change_in_inventories", "employee_benefits_expense",
    "other_expenses", "depreciation_amortisation", "finance_costs", "exceptional_items",
    "profit_before_tax", "tax_expense", "profit_for_the_year", "profit_attributable_to_owners",
    "total_equity", "equity_attributable_to_owners", "borrowings_non_current",
    "borrowings_current", "cash_and_cash_equivalents", "other_bank_balances",
    "current_investments", "inventories", "trade_receivables", "trade_payables",
    "total_assets", "total_equity_and_liabilities",
    "net_cash_from_operating_activities", "capital_expenditure",
}


def test_all_required_items_are_defined():
    items = set(load_line_items()["item_code"])
    missing = REQUIRED_ITEMS - items
    assert not missing, f"missing line items: {missing}"


def test_item_codes_are_unique():
    assert load_line_items()["item_code"].is_unique


def test_every_item_has_valid_statement_and_text():
    items = load_line_items()
    assert set(items["statement"]) <= {"PL", "BS", "CF"}
    for column in ["label", "definition", "sign_convention"]:
        assert items[column].notna().all(), f"empty {column}"
        assert (items[column].str.strip() != "").all(), f"blank {column}"
