
"""Compare extracted fields and clerk entries with photo-verified values.

Ground truth is audit/photo_field_truth.csv: fields read from the receipt
photos themselves (never copied from clerk entries). UNKNOWN marks a field
that could not be read from the photo; it is left out of every denominator
and counted separately. NONE in the gstin column means no GSTIN is printed.

Match rules:
  vendor          letters and digits only, case-insensitive
  receipt_date    same ISO date (YYYY-MM-DD)
  receipt_number  letters and digits only, case-insensitive
  gstin           exact; for NONE, a blank value is correct
  total_amount    within Rs 0.01
  A blank extracted value counts as a miss.

The sample deliberately over-represents difficult and changed extractions, so
its results are not a dataset-wide accuracy estimate; results for the random
picks alone are reported separately.

Usage (from the project root):
    python scripts/evaluate_photo_truth.py [--output PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.normalization import normalize_amount, normalize_date
from scripts.generate_predictions import filename_key

TRUTH_FILE = ROOT / "audit" / "photo_field_truth.csv"
OLD_FILE = ROOT / "reports" / "ocr_extractions_v2.csv"
NEW_FILE = ROOT / "reports" / "ocr_extractions_v3.csv"
CLAIMS_FILE = ROOT / "data" / "Task 2 Files" / "claims_train.csv"
OUTPUT_FILE = ROOT / "reports" / "photo_field_evaluation.md"

FIELDS = ["vendor", "receipt_date", "receipt_number", "gstin", "total_amount"]
CLERK = {
    "vendor": "clerk_vendor", "receipt_date": "clerk_bill_date",
    "receipt_number": "clerk_bill_no", "gstin": "clerk_gstin",
    "total_amount": "clerk_bill_amount",
}
UNKNOWN, NONE = "UNKNOWN", "NONE"


def _alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def matches(field: str, truth: str, value: str) -> bool:
    value = (value or "").strip()
    if field == "gstin":
        return value == "" if truth == NONE else value.upper() == truth.upper()
    if not value:
        return False
    if field == "receipt_date":
        return (normalize_date(value) or value) == truth
    if field == "total_amount":
        amount = normalize_amount(value)
        return amount is not None and abs(amount - Decimal(truth)) <= Decimal("0.01")
    return _alnum(value) == _alnum(truth)


def score(sample: pd.DataFrame, column_of) -> dict[str, tuple[int, int, int]]:
    """field -> (correct, compared, unknown) over rows that have a value source."""
    result = {}
    for field in FIELDS:
        known = sample[sample[field] != UNKNOWN]
        compared = known[known[column_of(field)].notna()]
        correct = sum(
            matches(field, truth, value)
            for truth, value in zip(compared[field], compared[column_of(field)])
        )
        result[field] = (correct, len(compared), int((sample[field] == UNKNOWN).sum()))
    return result


def build_report() -> str:
    truth = pd.read_csv(TRUTH_FILE, dtype=str, keep_default_na=False)
    old = pd.read_csv(OLD_FILE, dtype=str, keep_default_na=False).set_index("image_filename")
    new = pd.read_csv(NEW_FILE, dtype=str, keep_default_na=False).set_index("image_filename")
    claims = pd.read_csv(CLAIMS_FILE, dtype=str, keep_default_na=False)
    claims["key"] = claims["image_file"].map(filename_key)
    clerk = claims.set_index("key")

    sample = truth.copy()
    for field in FIELDS:
        sample[f"old_{field}"] = sample["image_filename"].map(old[field])
        sample[f"new_{field}"] = sample["image_filename"].map(new[field])
        keys = sample["image_filename"].map(filename_key)
        sample[f"clerk_{field}"] = keys.map(
            lambda k, f=field: clerk[CLERK[f]].get(k) if k in clerk.index else None
        )

    random_count = int((sample["selection_reason"] == "random").sum())
    lines = [
        "# Photo-verified field evaluation",
        "",
        f"Sample: {len(sample)} receipt photos read directly from the images "
        f"(`audit/photo_field_truth.csv`): {random_count} drawn at random within "
        f"each layout family and {len(sample) - random_count} chosen deliberately "
        "as difficult or changed cases. Clerk values are compared only for "
        "sampled images that belong to training claims.",
        "",
        "## Sample composition",
        "",
        "| Layout family | Images | Random | Forced (difficult or changed) |",
        "|---|---|---|---|",
    ]
    for family, group in sample.groupby("layout_family"):
        random_count = int((group["selection_reason"] == "random").sum())
        lines.append(f"| {family} | {len(group)} | {random_count} | {len(group) - random_count} |")

    def table(title: str, rows: pd.DataFrame) -> None:
        old_s = score(rows, lambda f: f"old_{f}")
        new_s = score(rows, lambda f: f"new_{f}")
        clerk_s = score(rows, lambda f: f"clerk_{f}")
        lines.extend([
            "", f"## {title}", "",
            f"| Field | Unknown in photo | Old extraction ({OLD_FILE.name}) | New extraction ({NEW_FILE.name}) "
            "| Clerk entry vs photo (training claims only) |",
            "|---|---|---|---|---|",
        ])
        for field in FIELDS:
            (oc, on, unknown), (nc, nn, _), (cc, cn, _) = old_s[field], new_s[field], clerk_s[field]
            pct = lambda c, n: f"{c}/{n} ({c / n:.0%})" if n else "n/a"
            lines.append(f"| {field} | {unknown} | {pct(oc, on)} | {pct(nc, nn)} | {pct(cc, cn)} |")

    table("Photo-verified results, whole sample (difficult cases over-represented)", sample)
    table("Photo-verified results, random picks only", sample[sample["selection_reason"] == "random"])

    lines.extend(["", "## New extraction disagreements with the photo", ""])
    for field in FIELDS:
        bad = [
            (row["image_filename"][:3], row[field], row[f"new_{field}"] or "(blank)")
            for _, row in sample.iterrows()
            if row[field] != UNKNOWN and not matches(field, row[field], row[f"new_{field}"])
        ]
        lines.append(f"- **{field}** ({len(bad)}): " + ("; ".join(
            f"img {img}: photo `{t}`, extracted `{v}`" for img, t, v in bad) or "none"))

    lines.extend([
        "", "## Limitations", "",
        "- The photo readings are an AI-assisted reading of each image; no named reviewer.",
        "- GSTIN: printed O and 0 look alike; the PAN letter positions were recorded as letters, "
        "as the GSTIN format requires.",
        "- Altered totals are recorded as displayed on the bill (with a note); detecting the "
        "alteration is a separate check.",
        "- The sample is small and deliberately difficult; it does not estimate dataset-wide accuracy.",
        "- Random picks were drawn in fixed numbers per layout family, not in proportion to the "
        "dataset, so the random-only table is not a dataset-wide accuracy estimate either.",
        "- Processing coverage (all 467 images) is reported separately from this verified accuracy.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()
    report = build_report()
    args.output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
