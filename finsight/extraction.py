"""Read the consolidated statement pages and pick out each line item.

How it works, step by step:
  1. read_rows(): turn a PDF page into rows of (label, numbers), using the position
     of each word on the page. Pages with two printed pages side by side are read
     as a left half and a right half, so the two pages never get mixed.
  2. find_row(): for a line item, find the row whose label matches a pattern and take
     the last two numbers on it: (current year, previous year).
  3. extract_document(): do this for all 29 line items in one annual report.

The result is a DRAFT. Every value is then checked by the validation rules in
validation.py, and anything wrong is fixed in data/curated/corrections.csv with a
written reason, never by editing numbers silently.
"""

import re
from dataclasses import dataclass

import pymupdf

# A number as printed in the statements: 1,234.56  (1,234.56)  4132.22
NUMBER = re.compile(r"^\(?-?[\d,]+\.\d+\)?$")
DASHES = {"-", "–", "—"}  # a dash in a number column means nil


@dataclass
class Row:
    page: int        # PDF page number (starting at 1)
    label: str       # cleaned, lower-case label used for matching
    raw_label: str   # label as printed, kept for the record
    numbers: list    # number strings on the row, left to right
    section: str     # balance-sheet section the row sits in (see BS_SECTIONS)


def parse_number(text: str) -> float:
    """'(1,234.56)' -> -1234.56 ; '4132.22' -> 4132.22 ; '-' -> 0.0"""
    if text in DASHES:
        return 0.0
    negative = text.startswith("(") or text.startswith("-")
    value = float(text.strip("()-").replace(",", ""))
    return -value if negative else value


def clean_label(text: str) -> str:
    """Lower-case a label and remove leader dots, note numbers and list markers."""
    text = text.replace("‑", "-")                                  # non-breaking hyphen
    text = re.sub(r"\.{2,}", " ", text)                                 # "Inventories......"
    text = re.sub(r"^[\-–—•\s]+", "", text)                             # leading dash/bullet
    text = re.sub(r"^\(?([a-h]|i{1,3}|iv|v|\d{1,2})\)\s*", "", text, flags=re.I)  # "(a) ", "ii) "
    text = re.sub(r"\s+\d{1,2}[a-c]?(\([a-c]\))?$", "", text, flags=re.I)  # trailing note number
    return re.sub(r"\s+", " ", text).strip(" .:*").lower()


# Balance-sheet section headings. Some items (borrowings, investments) appear in more
# than one section, so we remember which section each row is in.
BS_SECTIONS = [
    # "\\b" rather than "$": page-edge navigation words sometimes join the heading line.
    (r"^non-current assets\b", "non_current_assets"),
    (r"^current assets\b", "current_assets"),
    (r"^(equity and liabilities|equity)$", "equity"),
    (r"^non-current liabilities\b", "non_current_liabilities"),
    (r"^current liabilities\b", "current_liabilities"),
]


def read_rows(pdf, page_number: int) -> list[Row]:
    """Return the rows of one PDF page. Two-pages-per-sheet pages are read half by half."""
    page = pdf[page_number - 1]
    rect = page.rect
    if rect.width > rect.height:  # landscape sheet = two printed pages side by side
        halves = [pymupdf.Rect(0, 0, rect.width / 2, rect.height),
                  pymupdf.Rect(rect.width / 2, 0, rect.width, rect.height)]
    else:
        halves = [rect]

    rows = []
    for clip in halves:
        words = page.get_text("words", clip=clip)  # each word: (x0, y0, x1, y1, text, ...)
        words.sort(key=lambda w: (round(w[3]), w[0]))
        lines = []  # words whose baselines are within 3 points belong to the same line
        for w in words:
            if lines and abs(lines[-1][0] - w[3]) < 3.0:
                lines[-1][1].append(w)
            else:
                lines.append([w[3], [w]])
        for _, line_words in lines:
            line_words.sort(key=lambda w: w[0])
            tokens = [w[4] for w in line_words]
            is_number = [bool(NUMBER.match(t)) or t in DASHES for t in tokens]
            numbers = [t for t, n in zip(tokens, is_number) if n]
            label = " ".join(t for t, n in zip(tokens, is_number) if not n)
            rows.append(Row(page_number, clean_label(label), label.strip(), numbers, ""))
    return rows


def add_sections(rows: list[Row]) -> list[Row]:
    """Tag each row with the balance-sheet section it falls under."""
    section = ""
    for row in rows:
        for pattern, name in BS_SECTIONS:
            if re.match(pattern, row.label):
                section = name
        row.section = section
    return rows


def last_two(row: Row):
    """Current-year and previous-year values = the last two numbers on the row."""
    if len(row.numbers) < 2:
        return None
    return parse_number(row.numbers[-2]), parse_number(row.numbers[-1])


def find_row(rows, pattern, exclude=None, section=None, wraps=False, start=0):
    """Find the first row (from `start`) whose label matches `pattern`.

    wraps=True: the label is long and printed over several lines, so the numbers may
    sit on one of the next 3 lines; we accept the first of those lines that has numbers.
    Returns (index, row_with_numbers, (current, previous)) or None.
    """
    for i in range(start, len(rows)):
        row = rows[i]
        if section and row.section != section:
            continue
        if not re.search(pattern, row.label):
            continue
        if exclude and re.search(exclude, row.label):
            continue
        candidates = rows[i: i + 4] if wraps else [row]
        for candidate in candidates:
            pair = last_two(candidate)
            if pair is not None:
                return i, candidate, pair
    return None


# Line item -> (statement, pattern, exclude, balance-sheet section, label wraps?)
ITEM_RULES = {
    "revenue_from_operations":      ("pl", r"^revenue from operations", None, None, False),
    "other_income":                 ("pl", r"^other income", None, None, False),
    "cost_of_materials_consumed":   ("pl", r"^cost of (raw )?materials? consumed", None, None, False),
    "purchases_of_stock_in_trade":  ("pl", r"^purchases? of (stock|traded)", None, None, False),
    # Wording varies: "Changes in inventories of...", "(Increase)/decrease in inventories of...",
    # "Increase in inventories of..."; all three contain "in inventories of".
    "change_in_inventories":        ("pl", r"in inventories of", None, None, True),
    "employee_benefits_expense":    ("pl", r"^employee benefits? expense", None, None, False),
    "finance_costs":                ("pl", r"^finance costs?", None, None, False),
    "depreciation_amortisation":    ("pl", r"^depreciation", None, None, False),
    "other_expenses":               ("pl", r"^other expenses", None, None, False),
    "share_of_profit_associates_jv": ("pl", r"^share of (net )?(profit|\(loss\)|loss)", r"comprehensive|\boci\b", None, False),
    "exceptional_items":            ("pl", r"^exceptional items?", None, None, False),
    "profit_before_exceptional":    ("pl", r"^profit before exceptional items?", None, None, True),
    "profit_before_tax":            ("pl", r"^(net )?profit before tax", None, None, False),
    "tax_expense":                  ("pl", r"^total tax expense", None, None, False),
    "profit_for_the_year":          ("pl", r"^(net )?(profit for the year|profit after tax)", r"attributable", None, False),
    "total_equity":                 ("bs", r"^total equity$", None, None, False),
    "equity_attributable_to_owners": ("bs", r"^equity attributable to", None, None, False),
    "non_controlling_interests":    ("bs", r"^non-controlling interests?", None, None, False),
    "borrowings_non_current":       ("bs", r"^borrowings", None, "non_current_liabilities", False),
    "borrowings_current":           ("bs", r"^borrowings", None, "current_liabilities", False),
    "cash_and_cash_equivalents":    ("bs", r"^cash and cash equivalents", None, "current_assets", False),
    "other_bank_balances":          ("bs", r"(bank balances other than|other balances with banks|^other bank balances)",
                                     None, "current_assets", False),
    "current_investments":          ("bs", r"^investments", None, "current_assets", False),
    "inventories":                  ("bs", r"^inventories", None, None, False),
    "trade_receivables":            ("bs", r"^trade receivables", None, "current_assets", False),
    "total_assets":                 ("bs", r"^total assets", None, None, False),
    "total_equity_and_liabilities": ("bs", r"^total equity and liabilities", None, None, False),
    "net_cash_from_operating_activities": ("cf", r"^net cash.*operating activities", None, None, False),
    "capital_expenditure":          ("cf", r"^purchase of (property|tangible)", None, None, True),
}

# Items that a company may simply not have. If the statement has no such line,
# the value is recorded as nil (0) WITH a note saying so, never silently.
MAY_BE_ABSENT = {
    "purchases_of_stock_in_trade", "share_of_profit_associates_jv", "exceptional_items",
    "other_bank_balances", "current_investments",
    "borrowings_non_current", "borrowings_current", "non_controlling_interests",
}


def statement_rows(pdf, pages: list[int]) -> list[Row]:
    """All rows from the given pages, in order, tagged with balance-sheet sections."""
    rows = []
    for p in pages:
        rows += read_rows(pdf, p)
    return add_sections(rows)


def extract_document(pdf_path, bs_page: int, pl_page: int, cf_page: int) -> list[dict]:
    """Extract every line item (current and previous year) from one annual report.

    Returns a list of dicts: item_code, current, previous, page, label_as_reported, method.
    """
    bs_page, pl_page, cf_page = int(bs_page), int(pl_page), int(cf_page)
    pdf = pymupdf.open(pdf_path)
    rows = {
        "bs": statement_rows(pdf, [bs_page]),
        "pl": statement_rows(pdf, [pl_page, pl_page + 1]),
        "cf": statement_rows(pdf, [cf_page, cf_page + 1]),
    }
    pdf.close()

    found = {}
    for item, (statement, pattern, exclude, section, wraps) in ITEM_RULES.items():
        hit = find_row(rows[statement], pattern, exclude, section, wraps)
        if hit:
            index, row, (current, previous) = hit
            found[item] = dict(current=current, previous=previous, page=row.page,
                               label_as_reported=rows[statement][index].raw_label, method="matched",
                               index=index)

    _add_special_items(rows, found)

    results = []
    for item, value in found.items():
        value.pop("index", None)
        results.append(dict(item_code=item, **value))
    for item in MAY_BE_ABSENT:
        if item not in found:
            results.append(dict(item_code=item, current=0.0, previous=0.0, page=None,
                                label_as_reported="", method="absent_nil"))
    return results


def _add_special_items(rows: dict, found: dict) -> None:
    """Items that need more than one row, or a fallback when no total line is printed."""
    pl, bs, cf = rows["pl"], rows["bs"], rows["cf"]

    # Revenue: Asian Paints prints only the parts (products + services + other operating revenue).
    if "revenue_from_operations" not in found:
        parts = [find_row(pl, p) for p in (r"^revenue from sale of products", r"^revenue from sale of services",
                                           r"^other operating revenue")]
        parts = [p for p in parts if p]
        if parts:
            found["revenue_from_operations"] = dict(
                current=round(sum(p[2][0] for p in parts), 2), previous=round(sum(p[2][1] for p in parts), 2),
                page=parts[0][1].page, label_as_reported=" + ".join(p[1].raw_label for p in parts),
                method="sum_of_parts")

    # Profit attributable to owners: the first "owners / equity holders" row after profit for the year.
    if "profit_for_the_year" in found:
        hit = find_row(pl, r"(owners of the (company|parent)|equity holders of the parent|shareholders of the company)",
                       start=found["profit_for_the_year"]["index"] + 1)
        if hit:
            index, row, (current, previous) = hit
            found["profit_attributable_to_owners"] = dict(
                current=current, previous=previous, page=row.page,
                label_as_reported=pl[index].raw_label, method="matched_after_profit")

    # Total equity: Asian Paints prints it as an unlabelled subtotal after non-controlling interests.
    if "total_equity" not in found and "non_controlling_interests" in found:
        start = found["non_controlling_interests"]["index"] + 1
        for row in bs[start: start + 2]:
            if row.label == "" and last_two(row):
                current, previous = last_two(row)
                found["total_equity"] = dict(current=current, previous=previous, page=row.page,
                                             label_as_reported="(unlabelled subtotal after non-controlling interests)",
                                             method="unlabelled_subtotal")
                break

    # Trade payables: either one line, or two lines (micro & small enterprises + others) to add up.
    hit = find_row(bs, r"^trade payables", section="current_liabilities")
    if hit:
        index, row, (current, previous) = hit
        found["trade_payables"] = dict(current=current, previous=previous, page=row.page,
                                       label_as_reported=row.raw_label, method="matched")
    else:
        heading = next((i for i, r in enumerate(bs)
                        if r.section == "current_liabilities" and r.label.startswith("trade payables")), None)
        if heading is not None:
            parts, i = [], heading + 1
            while len(parts) < 2 and i < len(bs):
                part = find_row(bs, r"outstanding dues", wraps=True, start=i)
                if not part:
                    break
                parts.append(part)
                i = part[0] + 1
            if len(parts) == 2:
                found["trade_payables"] = dict(
                    current=round(parts[0][2][0] + parts[1][2][0], 2),
                    previous=round(parts[0][2][1] + parts[1][2][1], 2),
                    page=parts[0][1].page, label_as_reported="Trade payables: MSME dues + other creditors",
                    method="sum_of_parts")

    # Exceptional items: companies print them with different signs (Asian Paints prints a loss
    # as a positive number and subtracts it). We store the EFFECT ON PROFIT, worked out from
    # the statement's own arithmetic: profit before tax - profit before exceptional items.
    if all(k in found for k in ("exceptional_items", "profit_before_exceptional", "profit_before_tax")):
        for column in ("current", "previous"):
            effect = round(found["profit_before_tax"][column] - found["profit_before_exceptional"][column], 2)
            printed = found["exceptional_items"][column]
            if abs(abs(effect) - abs(printed)) <= 0.02:
                found["exceptional_items"][column] = effect
            # if they disagree, the value is left as printed and validation will flag it

    # Total tax: Berger's FY2022 report prints the total as an unlabelled subtotal under
    # "Tax expense" (current tax + deferred tax).
    if "tax_expense" not in found:
        heading = next((i for i, r in enumerate(pl) if r.label == "tax expense" and not r.numbers), None)
        if heading is not None:
            for row in pl[heading + 1: heading + 6]:
                if row.label == "" and last_two(row):
                    current, previous = last_two(row)
                    found["tax_expense"] = dict(current=current, previous=previous, page=row.page,
                                                label_as_reported="(unlabelled subtotal under Tax expense)",
                                                method="unlabelled_subtotal")
                    break

    # With no exceptional items, profit before exceptional items is simply profit before tax.
    if "profit_before_exceptional" not in found and "exceptional_items" not in found and "profit_before_tax" in found:
        pbt = found["profit_before_tax"]
        found["profit_before_exceptional"] = dict(current=pbt["current"], previous=pbt["previous"], page=pbt["page"],
                                                  label_as_reported="(no exceptional items: equals profit before tax)",
                                                  method="equals_profit_before_tax")

    # Capital expenditure is printed as a cash outflow (negative); we store it as a positive amount.
    if "capital_expenditure" in found:
        found["capital_expenditure"]["current"] = abs(found["capital_expenditure"]["current"])
        found["capital_expenditure"]["previous"] = abs(found["capital_expenditure"]["previous"])
