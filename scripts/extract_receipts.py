
"""Batch-extract receipt fields into a CSV for review.

Usage (from the project root):
    python scripts/extract_receipts.py [--output PATH]

Writes reports/ocr_extractions_v3.csv by default. The earlier extraction
files (ocr_extractions.csv, ocr_extractions_v2.csv) are kept as records and
are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Add the project root so imports such as "from app.extraction" work.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.extraction import extract_receipt_fields


IMAGE_DIR = PROJECT_ROOT / "tarang-expense-receipts" / "images"
OUTPUT_CSV = PROJECT_ROOT / "reports" / "ocr_extractions_v3.csv"
PROTECTED_OUTPUTS = {
    PROJECT_ROOT / "reports" / "ocr_extractions.csv",
    PROJECT_ROOT / "reports" / "ocr_extractions_v2.csv",
}

# The first ten columns are unchanged from earlier extraction files.
COLUMNS = [
    "image_filename", "vendor", "receipt_date", "receipt_number", "gstin",
    "total_amount", "vehicle_no", "raw_text", "readable", "errors",
    "amount_in_words", "amount_in_words_value", "route_from", "route_to", "km",
    "fuel_rate_per_litre", "fuel_volume_litres", "notes",
    "filled_by_enhanced_pass", "raw_text_enhanced",
]


def csv_row(image_filename: str, fields: dict) -> dict:
    """One CSV row; blanks stay blank, nothing is filled in."""
    def text(value) -> str:
        return "" if value is None else str(value)

    return {
        "image_filename": image_filename,
        **{key: text(fields.get(key)) for key in COLUMNS[1:7]},
        "raw_text": fields.get("raw_text") or "",
        "readable": bool(fields.get("readable")),
        "errors": "; ".join(map(str, fields.get("errors", []))),
        **{key: text(fields.get(key)) for key in COLUMNS[10:17]},
        "notes": "; ".join(fields.get("notes", [])),
        "filled_by_enhanced_pass": "; ".join(fields.get("filled_by_enhanced_pass", [])),
        "raw_text_enhanced": fields.get("raw_text_enhanced") or "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    output_csv = parser.parse_args().output.resolve()
    if output_csv in PROTECTED_OUTPUTS:
        raise SystemExit(f"Refusing to overwrite {output_csv.name}; choose another --output.")

    if not IMAGE_DIR.is_dir():
        raise FileNotFoundError(
            f"Image directory not found: {IMAGE_DIR}"
        )

    images = sorted(
        path for path in IMAGE_DIR.iterdir() if path.is_file()
    )

    if not images:
        raise RuntimeError(f"No image files found in {IMAGE_DIR}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(images)} image files.")
    print("Starting OCR; the first image may take longer.")

    readable_count = 0
    missing_amount_count = 0
    error_count = 0

    with output_csv.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=COLUMNS,
            extrasaction="ignore",
        )
        writer.writeheader()

        for index, image_path in enumerate(images, start=1):
            fields = extract_receipt_fields(image_path)

            if fields.get("readable"):
                readable_count += 1

            if fields.get("total_amount") is None:
                missing_amount_count += 1

            errors = fields.get("errors", [])
            if errors:
                error_count += 1

            writer.writerow(csv_row(image_path.name, fields))

            if index % 10 == 0 or index == len(images):
                file.flush()
                print(f"Processed {index}/{len(images)} images")

    print(f"\nOCR extraction saved to: {output_csv}")
    print(f"Total images: {len(images)}")
    print(f"Readable images: {readable_count}/{len(images)}")
    print(f"Missing total amounts: {missing_amount_count}/{len(images)}")
    print(f"Images with extraction errors: {error_count}/{len(images)}")
    print("Review extracted fields before using them for claim decisions.")


if __name__ == "__main__":
    main()
