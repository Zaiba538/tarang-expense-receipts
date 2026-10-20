
from decimal import Decimal

from app.normalization import (
    normalize_text,
    normalize_vendor,
    normalize_amount,
    normalize_date,
    normalize_receipt_number,
    normalize_gstin,
    amounts_match,
)


def test_normalize_text_removes_extra_spaces():
    assert normalize_text("  Hello   World  ") == "Hello World"


def test_normalize_text_handles_missing_values():
    assert normalize_text(None) == ""
    assert normalize_text("nan") == ""
    assert normalize_text("  ") == ""


def test_normalize_vendor_preserves_readable_capitalization():
    assert normalize_vendor("  SHREE   GANESH TOURS & TRAVELS ") == (
        "SHREE GANESH TOURS & TRAVELS"
    )


def test_normalize_amount_parses_currency():
    assert normalize_amount("Rs 330") == Decimal("330")
    assert normalize_amount("1,234.50") == Decimal("1234.50")


def test_normalize_amount_handles_invalid_values():
    assert normalize_amount("") is None
    assert normalize_amount("not available") is None


def test_normalize_date_returns_iso_format():
    assert normalize_date("18/07/2026") == "2026-07-18"
    assert normalize_date("2026-07-18") == "2026-07-18"


def test_normalize_date_handles_invalid_values():
    assert normalize_date("") == ""
    assert normalize_date("not a date") == ""


def test_normalize_receipt_number_uses_uppercase():
    assert normalize_receipt_number(" sl92216340 ") == "SL92216340"


def test_normalize_gstin_uses_uppercase_and_removes_spaces():
    assert normalize_gstin(" 27hjxcw9975d1zj ") == "27HJXCW9975D1ZJ"


def test_amounts_match_allows_ten_rupees_difference():
    assert amounts_match("330", "340")
    assert amounts_match("340", "330")


def test_amounts_match_rejects_difference_over_ten_rupees():
    assert not amounts_match("330", "341")


def test_amounts_match_rejects_missing_amounts():
    assert not amounts_match("", "330")
