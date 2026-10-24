
"""Batch-extract receipt fields into a CSV for review.

Usage (from the project root):
    python scripts/extract_receipts.py [--output PATH]
    python scripts/extract_receipts.py --resume [--limit N] [--output PATH]

Writes reports/ocr_extractions_fresh.csv by default. The production
extraction files (ocr_extractions.csv, ocr_extractions_v2.csv,
ocr_extractions_v3.csv) are never overwritten. With --resume, images already
saved in the output are skipped and each new row is written to disk before
the next image, so an interrupted run can be continued.
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
OUTPUT_CSV = PROJECT_ROOT / "reports" / "ocr_extractions_fresh.csv"
# Production extraction files used by the pipeline are never overwritten.
PROTECTED_OUTPUTS = {
    PROJECT_ROOT / "reports" / "ocr_extractions.csv",
    PROJECT_ROOT / "reports" / "ocr_extractions_v2.csv",
    PROJECT_ROOT / "reports" / "ocr_extractions_v3.csv",
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


FAILURE_COLUMNS = ["image_filename", "error", "recorded_at"]
HARD_FAILURES = ("ocr_processing_failed", "image_file_not_found")


def completed_images(output_csv: Path, image_names: set[str]) -> set[str]:
    """Image filenames already saved in a checkpoint file, after checking it."""
    if not output_csv.exists():
        return set()
    with output_csv.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != COLUMNS:
            raise SystemExit(f"{output_csv.name} has different columns; not resuming.")
        rows = list(reader)
    if any(None in row.values() or None in row for row in rows):
        raise SystemExit(f"{output_csv.name} has an incomplete row; check its last line before resuming.")
    names = [row["image_filename"] for row in rows]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    unknown = sorted(set(names) - image_names)
    if duplicates or unknown:
        raise SystemExit(f"Checkpoint problem: duplicates {duplicates}, unknown images {unknown}.")
    return set(names)


def run_resumable(images: list[Path], output_csv: Path, failures_csv: Path, limit: int | None) -> None:
    """
    OCR only the images not yet saved in output_csv, one at a time. Each
    successful row is flushed to disk before the next image, so an
    interruption loses at most the image in progress. Images whose OCR failed
    go to failures_csv instead and are retried on the next resume.
    """
    import gc
    import os
    from datetime import datetime

    done = completed_images(output_csv, {path.name for path in images})
    todo = [path for path in images if path.name not in done]
    print(f"{len(done)} of {len(images)} images already saved; {len(todo)} to do.", flush=True)
    if limit is not None:
        todo = todo[:limit]

    new_file = not output_csv.exists()
    with output_csv.open("a", newline="", encoding="utf-8-sig" if new_file else "utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        for path in todo:
            fields = extract_receipt_fields(path)
            hard = [str(error) for error in fields.get("errors", []) if str(error).startswith(HARD_FAILURES)]
            if hard:
                new_log = not failures_csv.exists()
                with failures_csv.open("a", newline="", encoding="utf-8") as log:
                    log_writer = csv.DictWriter(log, fieldnames=FAILURE_COLUMNS)
                    if new_log:
                        log_writer.writeheader()
                    log_writer.writerow({
                        "image_filename": path.name,
                        "error": "; ".join(hard),
                        "recorded_at": datetime.now().isoformat(timespec="seconds"),
                    })
                print(f"FAILED {path.name}: {'; '.join(hard)}", flush=True)
            else:
                writer.writerow(csv_row(path.name, fields))
                file.flush()
                os.fsync(file.fileno())
                done.add(path.name)
                print(f"saved {len(done)}/{len(images)}: {path.name}", flush=True)
            del fields
            gc.collect()

    remaining = len(images) - len(completed_images(output_csv, {path.name for path in images}))
    print(f"Saved images: {len(images) - remaining}/{len(images)}; remaining: {remaining}.")
    if failures_csv.exists():
        print(f"Failures are logged in {failures_csv} and retried on the next --resume run.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--resume", action="store_true",
                        help="continue a checkpointed run, skipping images already saved")
    parser.add_argument("--limit", type=int, default=None,
                        help="with --resume: process at most this many images in this run")
    parser.add_argument("--failures", type=Path, default=None,
                        help="with --resume: CSV for failed images (default: <output>_failures.csv)")
    args = parser.parse_args()
    output_csv = args.output.resolve()
    if output_csv in PROTECTED_OUTPUTS:
        raise SystemExit(f"Refusing to overwrite {output_csv.name}; choose another --output.")
    if not args.resume and output_csv.exists():
        raise SystemExit(f"{output_csv.name} exists; use --resume to continue it or choose another --output.")

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

    if args.resume:
        failures_csv = (args.failures or output_csv.with_name(output_csv.stem + "_failures.csv")).resolve()
        run_resumable(images, output_csv, failures_csv, args.limit)
        return

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
