"""Milestone 2: build the financial dataset from the annual report PDFs.

Run from the project folder:
    python scripts/build_dataset.py

Step 1 reads the 45 statement pages and writes the draft (data/curated/extracted_values.csv).
Step 2 applies corrections and notes and writes data/curated/reported_values.csv.
Then run `python scripts/validate_data.py` to check the result.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from finsight.config import EXTRACTED_CSV, REPORTS_DIR  # noqa: E402
from finsight.dataset import build_and_save  # noqa: E402
from finsight.documents import load_documents  # noqa: E402
from finsight.extraction import extract_document  # noqa: E402


def extract_all() -> pd.DataFrame:
    rows = []
    for _, doc in load_documents().iterrows():
        values = extract_document(REPORTS_DIR / doc["file_name"],
                                  int(doc["bs_page"]), int(doc["pl_page"]), int(doc["cf_page"]))
        for v in values:
            rows.append(dict(company_id=doc["company_id"], fiscal_year=int(doc["fiscal_year"]),
                             document_id=doc["document_id"], **v))
        print(f"{doc['document_id']:<22} {len(values)} items extracted")
    draft = pd.DataFrame(rows)
    draft["page"] = draft["page"].astype("Int64")
    return draft.sort_values(["company_id", "fiscal_year", "item_code"])


def main() -> None:
    draft = extract_all()
    draft.to_csv(EXTRACTED_CSV, index=False)
    print(f"\nDraft written: {EXTRACTED_CSV.name} ({len(draft)} rows)")
    data = build_and_save()
    print(f"Dataset written: reported_values.csv ({len(data)} rows: "
          f"{data['company_id'].nunique()} companies x {data['fiscal_year'].nunique()} years x "
          f"{data['item_code'].nunique()} items)")
    print("Methods used:", data["method"].value_counts().to_dict())


if __name__ == "__main__":
    main()
