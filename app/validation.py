
"""Validation checks for extracted Tarang Pharma receipt fields."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.normalization import (
    amounts_match,
    normalize_amount,
    normalize_date,
    normalize_gstin,
    normalize_text,
)


GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)


def validate_gstin(value: object) -> bool:
    """Validate GSTIN format; an absent GSTIN is not itself an error."""
    gstin = normalize_gstin(value)
    if not gstin:
        return True
    return bool(GSTIN_PATTERN.fullmatch(gstin))


def _parse_amount_for_validation(value: object) -> Decimal | None:
    """Parse an amount while preserving negative values for validation."""
    if value is None or isinstance(value, bool):
        return None

    raw = str(value).strip()
    if not raw:
        return None

    # Parse the original sign before using the normalizer, which may
    # reject negative amounts as unsuitable receipt totals.
    cleaned = (
        raw.replace("₹", "")
        .replace("â‚¹", "")
        .replace(",", "")
        .strip()
    )
    cleaned = re.sub(r"(?i)\bINR\b|\bRs\.?|\brupees?\b", "", cleaned)
    cleaned = cleaned.strip()

    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        amount = None

    if amount is not None and amount.is_finite():
        return amount

    normalized = normalize_amount(value)
    if normalized is None:
        return None

    return Decimal(str(normalized))


def validate_receipt_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """
    Check extracted receipt fields without guessing missing values.

    Expected keys:
      vendor, receipt_date, receipt_number, gstin, total_amount
    """
    vendor = normalize_text(fields.get("vendor"))
    receipt_date = normalize_date(fields.get("receipt_date"))
    receipt_number = normalize_text(fields.get("receipt_number"))
    gstin = normalize_gstin(fields.get("gstin"))
    raw_amount = fields.get("total_amount")
    parsed_amount = _parse_amount_for_validation(raw_amount)

    errors: list[str] = []

    if not vendor:
        errors.append("vendor_missing")

    if not receipt_date:
        errors.append("receipt_date_missing_or_unreadable")

    if not receipt_number:
        errors.append("receipt_number_missing_or_unreadable")

    if parsed_amount is None:
        errors.append("total_amount_missing_or_unreadable")
    elif parsed_amount < 0:
        errors.append("total_amount_invalid")

    if gstin and not validate_gstin(gstin):
        errors.append("gstin_invalid_format")

    # Keep the public normalized output consistent with the existing API.
    normalized_amount = normalize_amount(raw_amount)
    if parsed_amount is not None and parsed_amount < 0:
        normalized_amount = parsed_amount

    return {
        "valid": not errors,
        "errors": errors,
        "normalized": {
            "vendor": vendor,
            "receipt_date": receipt_date,
            "receipt_number": receipt_number,
            "gstin": gstin,
            "total_amount": (
                float(normalized_amount)
                if normalized_amount is not None
                else None
            ),
        },
    }


def validate_claim_amount(
    amount_claimed: object,
    receipt_amount: object,
) -> dict[str, Any]:
    """Compare the claim with the receipt using the ₹10 policy tolerance."""
    claim_amount = normalize_amount(amount_claimed)
    bill_amount = normalize_amount(receipt_amount)

    if claim_amount is None:
        return {
            "matches": False,
            "reason": "claim_amount_missing_or_unreadable",
        }

    if bill_amount is None:
        return {
            "matches": False,
            "reason": "receipt_amount_missing_or_unreadable",
        }

    matches = amounts_match(claim_amount, bill_amount)

    return {
        "matches": matches,
        "reason": (
            "amount_matches_policy_tolerance"
            if matches
            else "claim_amount_differs_from_receipt"
        ),
        "claim_amount": float(claim_amount),
        "receipt_amount": float(bill_amount),
        "difference": float(abs(claim_amount - bill_amount)),
    }
