"""Pick 20 random values for a person to check by hand against the PDF pages.

Run from the project folder:
    python scripts/make_spot_check.py

This writes eval/spot_check.csv. Open each PDF at the page given, find the line item,
and type the number you see into the `value_in_pdf` column (exactly as printed, e.g.
1,234.56 or (12.30)). Then run `python scripts/validate_data.py`, which scores the result. If a first entry
turns out to be the checker's slip, keep it, and put the re-checked number and the reason in
`rechecked_value` and `review_note`.
NOTE: running this script again overwrites eval/spot_check.csv (and any entries in it).
The random seed is fixed, so the same 20 values are picked every time.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finsight.config import EVAL_DIR  # noqa: E402
from finsight.dataset import load_reported_values  # noqa: E402
from finsight.documents import load_documents, load_line_items  # noqa: E402

SAMPLE_SIZE = 20
SEED = 2026


def make_hint(row, layout: str) -> str:
    """Tell the checker anything that is not obvious about where or how to read the value."""
    hints = []
    if layout == "two_pages_per_sheet":
        hints.append("two printed pages side by side: look in both halves")
    if row["method"] == "sum_of_parts":
        hints.append("not printed as one line: add up the lines named in label_as_reported")
    if row["method"] == "unlabelled_subtotal":
        hints.append("the unlabelled subtotal line")
    if row["item_code"] == "exceptional_items":
        hints.append("type it exactly as printed; some companies print a loss without a minus sign, "
                     "while the dataset stores losses as negative, so only the size is compared")
    if row["item_code"] == "capital_expenditure":
        hints.append("printed in brackets as an outflow; stored as a positive amount")
    return "; ".join(hints)


def main() -> None:
    values = load_reported_values()
    # Only values that were read from a page (not nil lines or values equal to another line).
    values = values[~values["method"].isin(["absent_nil", "equals_profit_before_tax"])]
    sample = values.sample(n=SAMPLE_SIZE, random_state=SEED)

    docs = load_documents().set_index("document_id")
    labels = load_line_items().set_index("item_code")["label"]
    sample = sample.assign(
        file_name=sample["document_id"].map(docs["file_name"]),
        line_item=sample["item_code"].map(labels),
        which_column=[f"FY{y} column: the {'LEFT' if c == 'current' else 'RIGHT'}-hand number "
                      f"(the {'current' if c == 'current' else 'previous'} year in this report)"
                      for y, c in zip(sample["fiscal_year"], sample["column"])],
        label_as_reported=sample["label_as_reported"].map(lambda t: re.sub(r"\.{3,}", " ", t).strip()),
        hint=[make_hint(row, docs.loc[row["document_id"], "layout"]) for _, row in sample.iterrows()],
        value_in_pdf="",
        rechecked_value="",
        review_note="",
    )
    columns = ["company_id", "fiscal_year", "line_item", "label_as_reported", "value_cr", "file_name",
               "page", "which_column", "hint", "method", "value_in_pdf", "rechecked_value", "review_note"]
    EVAL_DIR.mkdir(exist_ok=True)
    out = EVAL_DIR / "spot_check.csv"
    sample[columns].sort_values(["company_id", "fiscal_year"]).to_csv(out, index=False)
    print(f"Wrote {out} with {SAMPLE_SIZE} values to check.")


if __name__ == "__main__":
    main()
