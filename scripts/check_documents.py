"""Milestone 1 check: are all annual reports present, unchanged and correctly indexed?

Run from the project folder:
    python scripts/check_documents.py
"""

import sys
from pathlib import Path

# Let this script import the "finsight" package from the project folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finsight.documents import check_document, load_documents  # noqa: E402


def main() -> int:
    documents = load_documents()
    passed = 0
    print(f"{'Document':<22} {'Pages':>5}  {'BS':>4} {'P&L':>4} {'CF':>4}  Result")
    print("-" * 60)
    for _, row in documents.iterrows():
        problems = check_document(row)
        result = "OK" if not problems else "FAIL"
        print(f"{row['document_id']:<22} {row['page_count']:>5}  "
              f"{row['bs_page']:>4} {row['pl_page']:>4} {row['cf_page']:>4}  {result}")
        for problem in problems:
            print(f"    - {problem}")
        passed += not problems

    total = len(documents)
    print("-" * 60)
    print(f"{passed}/{total} documents passed; "
          f"{passed * 3}/{total * 3} statement pages verified")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
