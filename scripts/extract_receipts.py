
"""Batch-extract receipt fields into a CSV for review."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Add the project root so imports such as "from app.extraction" work.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.extraction import extract_receipt_fields


IMAGE_DIR = PROJECT_ROOT / "tarang-expense-receipts" / "images"
OUTPUT_CSV = PROJECT_ROOT / "reports" / "ocr_extractions.csv"


def main() -> None:
    if not IMAGE_DIR.is_dir():
        raise FileNotFoundError(f"Image directory not found: {IMAGE_DIR}")

    images = sorted(path for path in IMAGE_DIR.iterdir() if path.is_file())

    if not images:
        raise RuntimeError(f"No image files found in {IMAGE_DIR}")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "image_filename",
        "vendor",
        "receipt_date",
        "receipt_number",
        "gstin",
        "total_amount",
        "vehicle_no",
        "readable",
        "errors",
    ]

    print(f"Found {len(images)} image files.")
    print("Starting OCR; the first image may take longer.")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        readable_count = 0
        missing_amount_count = 0

        for index, image_path in enumerate(images, start=1):
            fields = extract_receipt_fields(image_path)

            if fields["readable"]:
                readable_count += 1
            if fields["total_amount"] is None:
                missing_amount_count += 1

            writer.writerow({
                "image_filename": image_path.name,
                "vendor": fields["vendor"],
                "receipt_date": fields["receipt_date"],
                "receipt_number": fields["receipt_number"],
                "gstin": fields["gstin"],
                "total_amount": (
                    str(fields["total_amount"])
                    if fields["total_amount"] is not None else ""
                ),
                "vehicle_no": fields["vehicle_no"],
                "readable": fields["readable"],
                "errors": "; ".join(fields["errors"]),
            })

            if index % 10 == 0 or index == len(images):
                file.flush()
                print(f"Processed {index}/{len(images)} images")

    print(f"\nOCR extraction saved to: {OUTPUT_CSV}")
    print(f"Readable images: {readable_count}/{len(images)}")
    print(f"Missing total amounts: {missing_amount_count}/{len(images)}")
    print("Review extracted fields before using them for claim decisions.")


if __name__ == "__main__":
    main()
