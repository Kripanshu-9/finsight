"""Milestone 3: calculate all metrics and write a comparison summary.

Run from the project folder:
    python scripts/build_metrics.py

Writes:
  data/derived/metrics.csv   - every metric for every company and year (with blanks explained)
  eval/metrics_summary.md    - side-by-side comparison tables for reading and review
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from finsight.config import DERIVED_DIR, EVAL_DIR, METRIC_DEFINITIONS_CSV, METRICS_CSV  # noqa: E402
from finsight.dataset import load_reported_values, wide  # noqa: E402
from finsight.documents import load_companies  # noqa: E402
from finsight.metrics import compute_metrics  # noqa: E402

SUMMARY_METRICS = [
    "revenue_growth", "gross_margin", "ebitda_margin", "underlying_pbt_margin", "pat_margin",
    "roe", "roce", "net_cash", "free_cash_flow", "cash_conversion_pat", "cash_conversion_ebitda",
    "receivable_days", "inventory_days", "payable_days", "cash_conversion_cycle",
]


def format_value(value, unit: str) -> str:
    if pd.isna(value):
        return "–"
    if unit == "percent":
        return f"{value * 100:.1f}%"
    if unit == "INR crore":
        return f"{value:,.0f}"
    if unit == "times":
        return f"{value:.2f}x"
    return f"{value:.0f}"


def summary_markdown(metrics: pd.DataFrame, definitions: pd.DataFrame) -> str:
    names = load_companies().set_index("company_id")["short_name"]
    years = sorted(metrics["fiscal_year"].unique())
    lines = [f"# Metric comparison (generated {date.today().isoformat()})", "",
             "Calculated by `finsight/metrics.py` from `data/curated/reported_values.csv`. "
             "Amounts in INR crore. † = reported figure includes exceptional items (see flag in "
             "`data/derived/metrics.csv`). – = not meaningful (reason recorded in the same file).", ""]
    defs = definitions.set_index("metric_code")
    for code in SUMMARY_METRICS:
        d = defs.loc[code]
        title = d["name"] if d["basis"] in d["name"] else f"{d['name']} ({d['basis']})"
        lines += [f"## {title}", "", f"_{d['formula']}_", "",
                  "| Company | " + " | ".join(f"FY{y}" for y in years) + " |",
                  "|---|" + "---:|" * len(years)]
        for company in names.index:
            cells = []
            for y in years:
                row = metrics[(metrics["company_id"] == company) & (metrics["fiscal_year"] == y)
                              & (metrics["metric_code"] == code)].iloc[0]
                cells.append(format_value(row["value"], d["unit"]) + (" †" if row["flag"] else ""))
            lines.append(f"| {names[company]} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    definitions = pd.read_csv(METRIC_DEFINITIONS_CSV)
    metrics = compute_metrics(wide(load_reported_values()))
    metrics = metrics.merge(definitions[["metric_code", "name", "unit", "basis"]], on="metric_code")
    DERIVED_DIR.mkdir(exist_ok=True)
    metrics.to_csv(METRICS_CSV, index=False)
    print(f"Wrote {METRICS_CSV.name}: {len(metrics)} rows "
          f"({metrics['value'].notna().sum()} values, {metrics['value'].isna().sum()} blank with a reason, "
          f"{(metrics['flag'] != '').sum()} flagged for exceptional items)")
    EVAL_DIR.mkdir(exist_ok=True)
    (EVAL_DIR / "metrics_summary.md").write_text(summary_markdown(metrics, definitions), encoding="utf-8")
    print("Wrote eval/metrics_summary.md")


if __name__ == "__main__":
    main()
