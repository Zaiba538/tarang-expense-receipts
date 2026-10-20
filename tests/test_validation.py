
from app.validation import (
    validate_gstin,
    validate_receipt_fields,
    validate_claim_amount,
)


def valid_receipt():
    return {
        "vendor": "SHREE GANESH TOURS & TRAVELS",
        "receipt_date": "18/07/2026",
        "receipt_number": "3678",
        "gstin": "",
        "total_amount": "1120.00",
    }


def test_valid_receipt_passes_validation():
    result = validate_receipt_fields(valid_receipt())

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["normalized"]["receipt_date"] == "2026-07-18"
    assert result["normalized"]["total_amount"] == 1120.0


def test_missing_gstin_is_not_an_error():
    result = validate_receipt_fields(valid_receipt())

    assert result["valid"] is True
    assert result["normalized"]["gstin"] == ""


def test_missing_required_fields_are_reported():
    result = validate_receipt_fields({})

    assert result["valid"] is False
    assert "vendor_missing" in result["errors"]
    assert "receipt_date_missing_or_unreadable" in result["errors"]
    assert "receipt_number_missing_or_unreadable" in result["errors"]
    assert "total_amount_missing_or_unreadable" in result["errors"]


def test_invalid_gstin_is_reported():
    receipt = valid_receipt()
    receipt["gstin"] = "INVALID"

    result = validate_receipt_fields(receipt)

    assert result["valid"] is False
    assert "gstin_invalid_format" in result["errors"]


def test_valid_gstin_format_is_accepted():
    assert validate_gstin("27AAPFU0939F1ZV") is True


def test_empty_gstin_is_accepted():
    assert validate_gstin("") is True


def test_negative_receipt_amount_is_rejected():
    receipt = valid_receipt()
    receipt["total_amount"] = "-100"

    result = validate_receipt_fields(receipt)

    assert result["valid"] is False
    assert "total_amount_invalid" in result["errors"]


def test_claim_amount_within_ten_rupees_matches():
    result = validate_claim_amount("330", "340")

    assert result["matches"] is True
    assert result["difference"] == 10.0


def test_claim_amount_over_ten_rupees_difference_does_not_match():
    result = validate_claim_amount("330", "341")

    assert result["matches"] is False
    assert result["reason"] == "claim_amount_differs_from_receipt"


def test_missing_claim_amount_is_reported():
    result = validate_claim_amount("", "330")

    assert result["matches"] is False
    assert result["reason"] == "claim_amount_missing_or_unreadable"


def test_missing_receipt_amount_is_reported():
    result = validate_claim_amount("330", "")

    assert result["matches"] is False
    assert result["reason"] == "receipt_amount_missing_or_unreadable"
