
"""Normalization helpers for Tarang Pharma expense receipts."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def normalize_text(value: object) -> str:
    """Normalize whitespace and casing while preserving the original meaning."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null", "nat"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_vendor(value: object) -> str:
    """Normalize a vendor name for comparison; retain readable capitalization."""
    return normalize_text(value)


def normalize_amount(value: object) -> Optional[Decimal]:
    """Parse currency values such as 'Rs 330', '₹1,234.50' or '330.00'."""
    text = normalize_text(value)
    if not text:
        return None

    text = re.sub(r"(?i)\b(?:INR|Rs\.?)\b", "", text)
    text = text.replace("₹", "").replace(",", "").strip()
    text = re.sub(r"[^\d.\-]", "", text)

    if not text or text in {".", "-", "-."}:
        return None

    try:
        amount = Decimal(text)
        if not amount.is_finite():
            return None
        return amount
    except InvalidOperation:
        return None


def normalize_date(value: object) -> str:
    """Return a recognized date as YYYY-MM-DD; otherwise return an empty string."""
    text = normalize_text(value)
    if not text:
        return ""

    formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%d/%m/%y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return ""


def normalize_receipt_number(value: object) -> str:
    """Normalize whitespace around a receipt or invoice number."""
    return normalize_text(value).upper()


def normalize_gstin(value: object) -> str:
    """Normalize a GSTIN for comparison without creating one when absent."""
    text = normalize_text(value).upper()
    return re.sub(r"\s+", "", text)


def amounts_match(claimed: object, billed: object) -> bool:
    """Compare claimed and billed amounts, allowing the policy's ₹10 rounding."""
    claim_amount = normalize_amount(claimed)
    bill_amount = normalize_amount(billed)

    if claim_amount is None or bill_amount is None:
        return False

    return abs(claim_amount - bill_amount) <= Decimal("10")
