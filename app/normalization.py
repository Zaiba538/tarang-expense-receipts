
"""Normalization helpers for receipt OCR and expense claim validation."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


MIN_PLAUSIBLE_YEAR = 2000
MAX_PLAUSIBLE_YEAR = 2099


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.casefold() in {"", "nan", "none", "nat", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_vendor(value: Any) -> str:
    return normalize_text(value)


def normalize_amount(value: Any) -> Decimal | None:
    """Parse amounts like Rs. 30, ₹1,250.50, and INR 500 safely."""
    text = normalize_text(value)
    if not text:
        return None

    text = text.replace("₹", "").replace("â‚¹", "")
    text = re.sub(r"(?i)\bINR\b|\bRs\.?|\brupees?\b", "", text)
    text = text.replace(",", "").replace(" ", "").strip()

    # After removing currency labels, allow an optional sign and decimals.
    match = re.search(r"(?<![\d.])-?\d+(?:\.\d{1,2})?(?![\d.])", text)
    if not match:
        return None

    try:
        amount = Decimal(match.group(0))
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount < 0:
        return None

    return amount.quantize(Decimal("0.01"))


def normalize_date(value: Any) -> str:
    """Normalize supported dates to YYYY-MM-DD using day-first dates."""
    text = normalize_text(value)
    if not text:
        return ""

    text = re.sub(
        r"(?i)^\s*(?:date|dated|bill\s+date|invoice\s+date)\s*[:\-]?\s*",
        "",
        text,
    ).strip()
    text = text.replace(".", "/")

    formats = [
        "%Y-%m-%d", "%Y/%m/%d",
        "%d-%m-%Y", "%d/%m/%Y",
        "%d-%m-%y", "%d/%m/%y",
        "%d/%b/%Y", "%d-%b-%Y",
        "%d/%b/%y", "%d-%b-%y",
        "%d/%B/%Y", "%d-%B-%Y",
        "%d %b %Y", "%d %B %Y",
        "%d %b %y", "%d %B %y",
        "%b %d, %Y", "%B %d, %Y",
        "%b %d %Y", "%B %d %Y",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # OCR can misread a year ("2826") or glue a time onto it
        # ("13/06/2614:56"); an implausible year is not a date.
        if MIN_PLAUSIBLE_YEAR <= parsed.year <= MAX_PLAUSIBLE_YEAR:
            return parsed.strftime("%Y-%m-%d")

    return ""


def normalize_receipt_number(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).upper()


def normalize_gstin(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).upper()


def amounts_match(
    claimed: Any,
    billed: Any,
    tolerance: Decimal = Decimal("10"),
) -> bool:
    claimed_amount = normalize_amount(claimed)
    billed_amount = normalize_amount(billed)
    if claimed_amount is None or billed_amount is None:
        return False
    return abs(claimed_amount - billed_amount) <= tolerance
