"""Milestone 2: run every data check and write a short report to eval/data_validation.md.

Run from the project folder:
    python scripts/validate_data.py
"""

import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from finsight.config import (EVAL_DIR, EXTRACTED_CSV, SECOND_SOURCE_CSV, VALUE_NOTES_CSV)  # noqa: E402
from finsight.dataset import load_reported_values  # noqa: E402
from finsight.documents import load_companies, load_documents, load_line_items  # noqa: E402
from finsight.validation import check_spot_check, restatement_differences, run_all  # noqa: E402


def main() -> int:
    values = load_reported_values()
    extracted = pd.read_csv(EXTRACTED_CSV)
    second = pd.read_csv(SECOND_SOURCE_CSV)
    findings = run_all(values, extracted, pd.read_csv(VALUE_NOTES_CSV), load_line_items(),
                       load_documents(), load_companies()["company_id"].tolist(), second)

    spot_file = EVAL_DIR / "spot_check.csv"
    spot = pd.read_csv(spot_file, dtype={"value_in_pdf": str}) if spot_file.exists() else None
    if spot is not None:
        findings += check_spot_check(spot)

    counts = Counter(f.level for f in findings)
    comparisons = len(restatement_differences(extracted))
    lines = [
        f"# Data validation report ({date.today().isoformat()})", "",
        f"- Values checked: {len(values)} "
        f"({values['company_id'].nunique()} companies x {values['fiscal_year'].nunique()} years x "
        f"{values['item_code'].nunique()} line items)",
        f"- Accounting identities: 5 per statement column x {values.groupby(['company_id', 'fiscal_year']).ngroups} "
        f"company-years",
        f"- Cross-report comparisons (same figure read from two different reports): {comparisons}",
        f"- Second-source comparisons with Screener.in: {len(second) * 3}",
        (f"- Hand spot check: {sum(f.check == 'spot check' and f.level == 'INFO' for f in findings)} of "
         f"{len(spot)} values confirmed" if spot is not None else "- Hand spot check: not created yet"),
        f"- Result: **{counts.get('FAIL', 0)} FAIL**, {counts.get('WARN', 0)} WARN, {counts.get('INFO', 0)} INFO",
        "",
    ]
    for level in ["FAIL", "WARN", "INFO"]:
        selected = [f for f in findings if f.level == level]
        if selected:
            lines += [f"## {level}", ""]
            lines += [f"- [{f.check}] {f.company_id} FY{f.fiscal_year}: {f.message}" for f in selected]
            lines.append("")

    report = "\n".join(lines)
    print(report)
    EVAL_DIR.mkdir(exist_ok=True)
    (EVAL_DIR / "data_validation.md").write_text(report, encoding="utf-8")
    return 1 if counts.get("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
