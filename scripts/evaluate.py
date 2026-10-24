"""Evaluate training-claim decisions against historical clerk statuses.

Historical statuses are reference labels, not verified policy-compliance ground truth.
Only matched OCR evidence is used for receipt fields in this evaluation. The
receipt evidence passed to the decision engine (OCR text, image hash and the
employee vehicle registry) matches scripts/generate_predictions.py, so the
same integrity, duplicate, vehicle and threshold checks apply. Duplicates are
compared within the training claims only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.decision_engine import make_decision
from app.duplicate_detection import detect_duplicates
from scripts.generate_predictions import clean, filename_key, image_sha256, truthy

DATA_DIR = ROOT / "data" / "Task 2 Files"
REPORT_DIR = ROOT / "reports"
TRAIN_FILE = DATA_DIR / "claims_train.csv"
EMPLOYEE_FILE = DATA_DIR / "employees.csv"
OCR_FILE = REPORT_DIR / "ocr_extractions_v4.csv"
OUTPUT_FILE = REPORT_DIR / "training_evaluation.csv"
SUMMARY_FILE = REPORT_DIR / "evaluation_summary.txt"


def main() -> None:
    for path in (TRAIN_FILE, EMPLOYEE_FILE, OCR_FILE):
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    claims_df = pd.read_csv(TRAIN_FILE).fillna("")
    employees_df = pd.read_csv(EMPLOYEE_FILE).fillna("")
    ocr_df = pd.read_csv(OCR_FILE).fillna("")

    if "status" not in claims_df.columns:
        raise ValueError("claims_train.csv must contain a status column.")
    if "image_file" not in claims_df.columns:
        raise ValueError("claims_train.csv must contain an image_file column.")
    if "image_filename" not in ocr_df.columns:
        raise ValueError("ocr_extractions.csv must contain image_filename.")

    ocr_df["filename_key"] = ocr_df["image_filename"].map(filename_key)
    key_counts = ocr_df["filename_key"].value_counts()
    unique_ocr = ocr_df[
        ocr_df["filename_key"].ne("")
        & ocr_df["filename_key"].map(key_counts).eq(1)
    ]
    ocr_by_key = unique_ocr.set_index("filename_key").to_dict("index")

    employees = {
        clean(row.get("emp_id")): row
        for row in employees_df.to_dict("records")
        if clean(row.get("emp_id"))
    }
    vehicle_registry = {
        re.sub(r"[^A-Z0-9]", "", clean(row.get("vehicle_no")).upper()): emp_id
        for emp_id, row in employees.items()
        if clean(row.get("vehicle_no"))
    }

    claims = claims_df.to_dict("records")
    receipts: dict[str, dict[str, Any]] = {}

    for claim in claims:
        key = filename_key(claim.get("image_file"))
        ocr = ocr_by_key.get(key)
        claim_id = clean(claim.get("claim_id"))

        if ocr is None:
            receipts[claim_id] = {
                "vendor": "",
                "receipt_date": "",
                "receipt_number": "",
                "gstin": "",
                "total_amount": "",
                "vehicle_no": "",
                "readable": False,
                "_receipt_available": False,
            }
        else:
            receipts[claim_id] = {
                "vendor": clean(ocr.get("vendor")),
                "receipt_date": clean(ocr.get("receipt_date")),
                "receipt_number": clean(ocr.get("receipt_number")),
                "gstin": clean(ocr.get("gstin")),
                "total_amount": clean(ocr.get("total_amount")),
                "vehicle_no": clean(ocr.get("vehicle_no")),
                "raw_text": clean(ocr.get("raw_text")),
                "raw_text_enhanced": clean(ocr.get("raw_text_enhanced")),
                "filled_by_enhanced_pass": clean(ocr.get("filled_by_enhanced_pass")),
                "image_sha256": image_sha256(ocr.get("image_filename")),
                "readable": truthy(ocr.get("readable")),
                "_receipt_available": True,
            }

    duplicate_results = detect_duplicates(claims, receipts)
    results: list[dict[str, Any]] = []

    for claim in claims:
        claim_id = clean(claim.get("claim_id"))
        receipt = receipts.get(claim_id, {})
        receipt_for_decision = {
            key: value
            for key, value in receipt.items()
            if not key.startswith("_")
        }

        result = make_decision(
            claim=claim,
            receipt=receipt_for_decision,
            employee=employees.get(clean(claim.get("emp_id")), {}),
            receipt_available=bool(receipt.get("_receipt_available", False)),
            duplicate_info=duplicate_results.get(
                claim_id,
                {"duplicate_detected": False, "possible_matches": []},
            ),
            vehicle_registry=vehicle_registry,
        )

        historical_status = clean(claim.get("status")).casefold()
        if historical_status == "approved":
            reference_label = "approve"
        elif historical_status in {"queried", "rejected"}:
            reference_label = "review"
        else:
            reference_label = ""

        results.append({
            "claim_id": claim_id,
            "category": clean(claim.get("category")),
            "historical_status": historical_status,
            "reference_label": reference_label,
            "predicted_decision": clean(result.get("decision")),
            "reason": clean(result.get("reason")),
            "receipt_image_matched": bool(receipt.get("_receipt_available", False)),
            "receipt_vendor": clean(receipt.get("vendor")),
            "receipt_date": clean(receipt.get("receipt_date")),
            "receipt_number": clean(receipt.get("receipt_number")),
            "receipt_amount": clean(receipt.get("total_amount")),
        })

    evaluation = pd.DataFrame(results)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    evaluation.to_csv(OUTPUT_FILE, index=False)

    eligible = evaluation[evaluation["reference_label"].ne("")].copy()
    compared = len(eligible)
    correct = int(
        eligible["reference_label"].eq(eligible["predicted_decision"]).sum()
    )
    accuracy = correct / compared if compared else 0.0

    confusion = pd.crosstab(
        eligible["reference_label"],
        eligible["predicted_decision"],
        rownames=["Historical reference label"],
        colnames=["Predicted decision"],
        dropna=False,
    )

    status_counts = evaluation["historical_status"].value_counts().to_dict()
    prediction_counts = evaluation["predicted_decision"].value_counts().to_dict()
    matched_count = int(evaluation["receipt_image_matched"].sum())
    unmatched_count = len(evaluation) - matched_count

    lines = [
        "TARANG PHARMA — TRAINING EVALUATION",
        "=" * 42,
        "",
        "Interpretation:",
        "Historical statuses are reference labels, not verified policy-compliance truth.",
        "The comparison below measures agreement with historical labels only.",
        "",
        f"Training claims: {len(evaluation)}",
        f"Claims with a matched OCR image: {matched_count}",
        f"Claims without a matched OCR image: {unmatched_count}",
        f"Claims with a recognized historical reference label: {compared}",
        f"Label agreements: {correct}",
        f"Agreement with historical labels: {accuracy:.1%}",
        "",
        "Historical status counts:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in sorted(status_counts.items()))
    lines.extend(["", "Predicted decision counts:"])
    lines.extend(f"  {key}: {value}" for key, value in sorted(prediction_counts.items()))
    lines.extend(["", "Historical-label comparison:", confusion.to_string()])
    lines.extend([
        "",
        f"Detailed claim-level results: {OUTPUT_FILE.name}",
        "",
        "Limitations:",
        "- Missing receipt images are not evidence of misconduct or policy violation.",
        "- OCR extraction errors can affect the predicted decision.",
        "- Historical approvals, queries, and rejections may not reflect current policy.",
        "- Agreement is not proof of policy correctness or production readiness.",
        "- Some historically approved claims carry altered totals or duplicates found",
        "  in the photo audit; disagreeing with those approvals is intended.",
    ])

    SUMMARY_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print("\nSaved detailed results:", OUTPUT_FILE)
    print("Saved evaluation summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
