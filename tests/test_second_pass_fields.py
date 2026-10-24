"""Fields recovered by the enhanced second OCR pass (ocr_extractions_v4.csv)."""

import csv
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from app.decision_engine import make_decision
from app.integrity_checks import (
    check_receipt_integrity,
    enhanced_pass_fields,
    total_source_text,
)
from scripts.generate_predictions import require_reextracted

ROOT = Path(__file__).resolve().parents[1]

# Image 444 (CLM-31440): the first pass misread Chai "60" as "09" and could not
# read the "Total Rs." label; the second pass read both (110 + 45 + 30 + 60 = 245).
BILL_444_FIRST_PASS = (
    "HIGHWAY KING DHABA\nDate 2/8/26\nBill No. 1414\nParticulars\nAmount\n"
    "I Sev Bhaji\n110\n3Roti\n45\nIPoha\n30\n4Chai\n09\n245\no Rs"
)
BILL_444_SECOND_PASS = (
    "HIGHWAY KING DHABA\nDate 2/8/26\nBill No. 1414\nParticulars\nAmount\n"
    "110\nI Sev Bhaji\n3Roti\n45\n30\nIPoha\n60\n4 Chai\n245\nTotal Rs."
)


def read_csv(path):
    with open(ROOT / path, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def by_image(rows):
    return {row["image_filename"][:3]: row for row in rows}


def test_enhanced_pass_fields_reads_lists_and_csv_strings():
    assert enhanced_pass_fields({"filled_by_enhanced_pass": ["receipt_date"]}) == ["receipt_date"]
    assert enhanced_pass_fields({"filled_by_enhanced_pass": "total_amount; vehicle_no"}) == [
        "total_amount", "vehicle_no",
    ]
    assert enhanced_pass_fields({}) == []


def test_total_is_checked_on_the_pass_it_was_read_from():
    receipt = {
        "raw_text": BILL_444_FIRST_PASS,
        "raw_text_enhanced": BILL_444_SECOND_PASS,
        "filled_by_enhanced_pass": "total_amount",
    }
    assert total_source_text(receipt) == BILL_444_SECOND_PASS
    # Mixing passes raised a false warning; the total's own pass supports it.
    assert check_receipt_integrity(BILL_444_FIRST_PASS, "245.00")
    assert check_receipt_integrity(total_source_text(receipt), "245.00") == []


def test_first_pass_total_is_still_checked_on_the_first_pass():
    receipt = {
        "raw_text": BILL_444_FIRST_PASS,
        "raw_text_enhanced": BILL_444_SECOND_PASS,
        "filled_by_enhanced_pass": "receipt_date",
    }
    assert total_source_text(receipt) == BILL_444_FIRST_PASS


def test_second_pass_total_that_the_bill_does_not_support_is_flagged():
    receipt = {
        "raw_text": "",
        "raw_text_enhanced": BILL_444_SECOND_PASS.replace("\n245\n", "\n1245\n"),
        "filled_by_enhanced_pass": "total_amount",
    }
    codes = [f["code"] for f in check_receipt_integrity(total_source_text(receipt), "1245.00")]
    assert codes == ["total_not_supported_by_line_items"]


def make_claim():
    return {"claim_id": "CLM-TEST-2P", "category": "parking", "amount_claimed": 30}


def make_receipt(**extra):
    return {
        "vendor": "SITABULDI MULTILEVEL PARKING",
        "receipt_date": "2026-07-30",
        "receipt_number": "118340",
        "gstin": "",
        "total_amount": 30,
        "readable": True,
        **extra,
    }


def test_recovered_field_alone_never_approves():
    approved = make_decision(make_claim(), make_receipt(), {"emp_id": "EMP-001", "grade": "M1"})
    assert approved["decision"] == "approve"

    recovered = make_decision(
        make_claim(),
        make_receipt(filled_by_enhanced_pass=["receipt_date"]),
        {"emp_id": "EMP-001", "grade": "M1"},
    )
    assert recovered["decision"] == "review"
    assert "read_on_second_pass" in recovered["flags"]
    assert recovered["reason"] == (
        "Receipt date read only on a second, enhanced OCR pass; "
        "confirm against the photo before payment."
    )


def test_second_pass_reason_names_every_recovered_field():
    result = make_decision(
        make_claim(),
        make_receipt(filled_by_enhanced_pass="total_amount; vehicle_no; amount_in_words"),
        {"emp_id": "EMP-001", "grade": "M1"},
    )
    assert "Total amount and vehicle number read only on a second" in result["reason"]


def test_raw_ocr_run_is_refused_as_prediction_input():
    with pytest.raises(ValueError, match="reextract_from_raw_text"):
        require_reextracted(ROOT / "reports" / "ocr_extractions_fresh.csv")
    require_reextracted(ROOT / "reports" / "ocr_extractions_v4.csv")


def test_v4_differs_from_v3_only_in_second_pass_recoveries():
    v3 = by_image(read_csv("reports/ocr_extractions_v3.csv"))
    v4 = by_image(read_csv("reports/ocr_extractions_v4.csv"))
    assert set(v3) == set(v4)
    changed = {
        image for image in v3
        if any(v3[image][c] != v4[image][c] for c in v3[image] if c not in ("raw_text_enhanced", "filled_by_enhanced_pass"))
    }
    assert changed == {"275", "388", "417", "444", "456", "459", "462"}
    assert all(v3[image]["raw_text"] == v4[image]["raw_text"] for image in v3)

    assert v4["417"]["receipt_date"] == "2026-07-30"
    assert v4["462"]["receipt_number"] == "8354"
    assert v4["459"]["receipt_date"] == "2026-08-05"
    assert v4["459"]["total_amount"] == "1082.00"
    assert v4["459"]["receipt_number"] == ""
    assert v4["388"]["total_amount"] == "1100.00"
    assert v4["388"]["vehicle_no"] == "MH34CP1653"
    assert v4["444"]["total_amount"] == "245.00"
    assert v4["275"]["receipt_date"] == "2026-07-01"
    assert v4["456"]["vehicle_no"] == "MH32CP8817"


def test_earlier_extraction_fixes_survive_in_v4():
    v3 = by_image(read_csv("reports/ocr_extractions_v3.csv"))
    v4 = by_image(read_csv("reports/ocr_extractions_v4.csv"))
    # A Km reading (187) and an item price (192) are not bill totals.
    assert v4["187"]["total_amount"] == ""
    assert v4["192"]["total_amount"] == ""
    # Every plate recovered by the dataset-wide extraction rules is kept.
    for image, row in v3.items():
        if row["vehicle_no"]:
            assert v4[image]["vehicle_no"] == row["vehicle_no"], image


def test_388_total_stays_probable_in_the_photo_audit():
    checks = [
        row for row in read_csv("audit/photo_checks_followup.csv")
        if row["image_id"] == "388" and row["field_or_risk"] == "total_amount"
    ]
    assert [row["confidence"] for row in checks] == ["probable"]


def test_predictions_keep_recovered_claims_in_review():
    predictions = {row["claim_id"]: row for row in read_csv("predictions.csv")}
    assert Counter(row["decision"] for row in predictions.values()) == {"approve": 80, "review": 110}
    for claim_id in ("CLM-31356", "CLM-31486", "CLM-31440", "CLM-31244", "CLM-31478"):
        assert predictions[claim_id]["decision"] == "review", claim_id
        assert "read only on a second, enhanced OCR pass" in predictions[claim_id]["reason"]
    assert predictions["CLM-31356"]["receipt_date"] == "2026-07-30"
    assert predictions["CLM-31486"]["receipt_number"] == "8354"
    assert predictions["CLM-31440"]["total_amount"] == "245.00"
    assert "not supported by the bill's own figures" not in predictions["CLM-31440"]["reason"]
    # 459's subtotal misread is a known false warning, left for manual review.
    assert "not supported by the bill's own figures" in predictions["CLM-31478"]["reason"]


def test_ledger_counted_exposure_is_unchanged_by_v4():
    totals = Counter()
    for row in read_csv("reports/audit_exposure_ledger.csv"):
        if row["counted_in_totals"] == "True":
            totals[(row["split"], row["finding_category"])] += Decimal(row[row["counted_measure"]])
    assert totals[("test", "confirmed_photo")] == Decimal("9304.23")
    assert totals[("test", "probable_photo")] == Decimal("2000.00")
    assert totals[("test", "ocr_lead")] == Decimal("3196.80")
    assert totals[("train", "confirmed_photo")] == Decimal("10878.00")
