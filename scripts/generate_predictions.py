
"""Generate the required predictions.csv for Tarang Pharma claims."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.decision_engine import make_decision
from app.duplicate_detection import detect_duplicates

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "Task 2 Files"
REPORT_DIR = ROOT / "reports"
OCR_FILE = REPORT_DIR / "ocr_extractions.csv"
OUTPUT_FILE = ROOT / "predictions.csv"

SUBMISSION_COLUMNS = [
    "claim_id",
    "vendor",
    "receipt_date",
    "receipt_number",
    "gstin",
    "total_amount",
    "decision",
    "reason",
]


def clean(value: Any) -> str:
    """Convert a CSV value to a clean string, treating missing values as blank."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def filename_key(value: Any) -> str:
    """Normalize an original image filename, ignoring directories and extension."""
    name = clean(value).replace("\\", "/").split("/")[-1]

    # Downloaded OCR filenames have: index_UUID-original_filename
    match = re.match(
        r"^\d+_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12}-(.+)$",
        name,
    )
    if match:
        name = match.group(1)

    return Path(name).stem.casefold()


def amount_for_csv(value: Any) -> str:
    """Format a known amount without inventing a value."""
    text = clean(value)
    if not text:
        return ""
    try:
        number = float(text.replace(",", "").replace("₹", "").strip())
        if not pd.notna(number):
            return ""
        return f"{number:.2f}"
    except (TypeError, ValueError):
        return ""


def truthy(value: Any) -> bool:
    return clean(value).casefold() in {
        "true", "1", "yes", "y", "present", "available"
    }


def main() -> None:
    train_path = DATA_DIR / "claims_train.csv"
    test_path = DATA_DIR / "claims_test.csv"
    employees_path = DATA_DIR / "employees.csv"
    submission_path = DATA_DIR / "sample_submission.csv"

    for path in [train_path, test_path, employees_path, submission_path, OCR_FILE]:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    train = pd.read_csv(train_path).fillna("")
    test = pd.read_csv(test_path).fillna("")
    employees_df = pd.read_csv(employees_path).fillna("")
    sample = pd.read_csv(submission_path)

    if list(sample.columns) != SUBMISSION_COLUMNS:
        raise ValueError(
            "sample_submission.csv columns do not match the expected schema: "
            f"{sample.columns.tolist()}"
        )

    if len(test) != len(sample):
        raise ValueError(
            f"Test has {len(test)} rows but sample submission has {len(sample)}."
        )

    ocr_df = pd.read_csv(OCR_FILE).fillna("")
    ocr_df["filename_key"] = ocr_df["image_filename"].map(filename_key)

    # Only use OCR filenames that identify one unique record.
    counts = ocr_df["filename_key"].value_counts()
    unique_ocr = ocr_df[
        ocr_df["filename_key"].ne("")
        & ocr_df["filename_key"].map(counts).eq(1)
    ]
    ocr_by_key = unique_ocr.set_index("filename_key").to_dict("index")

    employees = {
        clean(row.get("emp_id")): row
        for row in employees_df.to_dict("records")
        if clean(row.get("emp_id"))
    }

    def receipt_for_claim(claim: dict[str, Any]) -> dict[str, Any]:
        key = filename_key(claim.get("image_file"))
        ocr = ocr_by_key.get(key)

        if ocr is not None:
            return {
                "vendor": clean(ocr.get("vendor")),
                "receipt_date": clean(ocr.get("receipt_date")),
                "receipt_number": clean(ocr.get("receipt_number")),
                "gstin": clean(ocr.get("gstin")),
                "total_amount": clean(ocr.get("total_amount")),
                "vehicle_no": clean(ocr.get("vehicle_no")),
                "readable": truthy(ocr.get("readable")),
                "gst_tax_invoice": False,
                "driver_receipt": False,
                "_receipt_available": True,
            }

        # Training data can still supply historical clerk fields for
        # duplicate comparison. These are not used as test OCR evidence.
        has_clerk_fields = any(
            clean(claim.get(field))
            for field in [
                "clerk_vendor",
                "clerk_bill_date",
                "clerk_bill_no",
                "clerk_bill_amount",
                "clerk_gstin",
            ]
        )

        if has_clerk_fields:
            return {
                "vendor": clean(claim.get("clerk_vendor")),
                "receipt_date": clean(claim.get("clerk_bill_date")),
                "receipt_number": clean(claim.get("clerk_bill_no")),
                "gstin": clean(claim.get("clerk_gstin")),
                "total_amount": clean(claim.get("clerk_bill_amount")),
                "readable": True,
                "_receipt_available": False,
            }

        return {
            "vendor": "",
            "receipt_date": "",
            "receipt_number": "",
            "gstin": "",
            "total_amount": "",
            "readable": False,
            "_receipt_available": False,
        }

    train_records = train.to_dict("records")
    test_records = test.to_dict("records")
    all_claims = train_records + test_records

    # Build receipt evidence for duplicate checks across train and test.
    all_receipts: dict[str, dict[str, Any]] = {}
    for claim in all_claims:
        claim_id = clean(claim.get("claim_id"))
        if claim_id:
            all_receipts[claim_id] = receipt_for_claim(claim)

    duplicate_results = detect_duplicates(all_claims, all_receipts)

    # Historical training data uses clerk fields if OCR did not match.
    # The test decision itself always requires a matched OCR image.
    results: list[dict[str, str]] = []

    for claim in test_records:
        claim_id = clean(claim.get("claim_id"))
        receipt = all_receipts.get(claim_id, {})
        employee = employees.get(clean(claim.get("emp_id")), {})
        receipt_available = bool(receipt.get("_receipt_available", False))

        # Internal metadata is not part of the receipt schema.
        receipt_for_decision = {
            key: value
            for key, value in receipt.items()
            if not key.startswith("_")
        }

        duplicate_info = duplicate_results.get(
            claim_id,
            {"duplicate_detected": False, "possible_matches": []},
        )

        decision_result = make_decision(
            claim=claim,
            receipt=receipt_for_decision,
            employee=employee,
            receipt_available=receipt_available,
            duplicate_info=duplicate_info,
        )

        # Use the claim vendor only as a fallback display value; it does
        # not imply the receipt vendor was verified.
        vendor = clean(receipt.get("vendor")) or clean(claim.get("vendor"))

        results.append({
            "claim_id": claim_id,
            "vendor": vendor,
            "receipt_date": clean(receipt.get("receipt_date")),
            "receipt_number": clean(receipt.get("receipt_number")),
            "gstin": clean(receipt.get("gstin")),
            "total_amount": amount_for_csv(receipt.get("total_amount")),
            "decision": clean(decision_result.get("decision")) or "review",
            "reason": clean(decision_result.get("reason"))
            or "Manual review is required before payment.",
        })

    output = pd.DataFrame(results, columns=SUBMISSION_COLUMNS)

    # Preserve the sample submission's claim order.
    expected_ids = sample["claim_id"].map(clean).tolist()
    output_ids = output["claim_id"].map(clean).tolist()

    if output_ids != expected_ids:
        output_by_id = output.set_index("claim_id")
        if len(set(output_ids)) != len(output_ids):
            raise ValueError("Duplicate claim IDs were produced.")
        if set(output_ids) != set(expected_ids):
            raise ValueError("Generated claim IDs differ from sample submission.")
        output = output_by_id.loc[expected_ids].reset_index()

    if len(output) != 190:
        raise ValueError(f"Expected 190 predictions, generated {len(output)}.")

    if output["claim_id"].duplicated().any():
        raise ValueError("Duplicate claim IDs in predictions.")

    if not output["decision"].isin(["approve", "review"]).all():
        raise ValueError("Unexpected decision value found.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)

    print(f"Predictions saved: {OUTPUT_FILE}")
    print(f"Rows generated: {len(output)}")
    print("\nDecision counts:")
    print(output["decision"].value_counts(dropna=False).to_string())
    print("\nBlank receipt amounts:", int(output["total_amount"].eq("").sum()))
    print("Blank receipt dates:", int(output["receipt_date"].eq("").sum()))
    print("Blank receipt numbers:", int(output["receipt_number"].eq("").sum()))
    print("\nFirst five predictions:")
    print(output.head().to_string(index=False))


if __name__ == "__main__":
    main()
