
"""Re-apply the current field-extraction rules to stored OCR text.

OCR is the slow step; turning OCR text into fields is not. This script reads
the raw OCR text already saved for every image (and the enhanced second-pass
text, when present) and re-runs only the field rules (app.extraction.combine_passes),
so improved rules can be
applied to all images without re-running OCR. The input is never modified.

Only valid while the stored raw text matches what OCR currently produces for
the images (same images, same OCR configuration); re-run
scripts/extract_receipts.py when either changes.

Usage (from the project root):
    python scripts/reextract_from_raw_text.py [--input PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.extraction import combine_passes
from scripts.extract_receipts import COLUMNS, csv_row

INPUT_CSV = PROJECT_ROOT / "reports" / "ocr_extractions.csv"
OUTPUT_CSV = PROJECT_ROOT / "reports" / "ocr_extractions_v2.csv"
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    if args.input.resolve() == args.output.resolve():
        raise SystemExit("Refusing to overwrite the input OCR file.")

    with args.input.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    with args.output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            raw_text = row.get("raw_text") or ""
            enhanced = row.get("raw_text_enhanced") or ""
            fields = combine_passes(
                [line for line in raw_text.split("\n") if line.strip()],
                [line for line in enhanced.split("\n") if line.strip()] or None,
            )
            fields.update(
                raw_text=raw_text,
                raw_text_enhanced=enhanced,
                readable=bool(raw_text.strip() or enhanced.strip()),
            )
            writer.writerow(csv_row(row["image_filename"], fields))

    print(f"Re-extracted {len(rows)} rows from {args.input}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
