
from decimal import Decimal

from app.extraction import _extract_amount


def test_extracts_amount_after_total_label():
    assert _extract_amount("Total: Rs 536", ["Total: Rs 536"]) == Decimal("536")


def test_extracts_total_on_next_line():
    text = "Grand Total\nRs 1,234.50"
    assert _extract_amount(text, text.splitlines()) == Decimal("1234.50")


def test_extracts_total_when_label_precedes_amount_with_blank_line():
    text = "Total (INR)\n4,704.00"
    assert _extract_amount(text, text.splitlines()) == Decimal("4704.00")


def test_extracts_courier_total():
    text = "Freight\n50.40\nGST @18%\n330.40\nTOTAL Rs"
    assert _extract_amount(text, text.splitlines()) == Decimal("330.40")


def test_extracts_fuel_total():
    text = "Amount (Rs): 300.00\nVehicle No: MH31DX0981\n300.00\nTOTAL\nRs."
    assert _extract_amount(text, text.splitlines()) == Decimal("300.00")


def test_extracts_amount_before_amount_label():
    text = "1120/-\nAmount Rs.\nOne Thousand One Hundred Twenty only"
    assert _extract_amount(text, text.splitlines()) == Decimal("1120")


def test_extracts_parking_amount_before_label():
    text = "30.00\nAmount Rs\nVehicle parked at owner's risk"
    assert _extract_amount(text, text.splitlines()) == Decimal("30.00")


def test_prefers_labelled_total_over_tax():
    text = "Tax: Rs 50\nGrand Total: Rs 550"
    assert _extract_amount(text, text.splitlines()) == Decimal("550")


def test_does_not_guess_from_unlabelled_currency_amounts():
    text = "Item: Rs 50\nTax: Rs 10"
    assert _extract_amount(text, text.splitlines()) is None


def test_returns_none_when_no_amount_is_present():
    assert _extract_amount("No amount shown", ["No amount shown"]) is None


def test_extracts_parking_amount_before_unlabelled_text():
    text = (
        "Ticket No: 112378\n"
        "30.00\n"
        "Vehicle parked at owner's risk"
    )
    assert _extract_amount(text, text.splitlines()) == Decimal("30.00")


def test_extracts_restaurant_total_after_itemized_amounts():
    text = (
        "Particulars\n"
        "Amount\n"
        "Paneer Bhurji\n"
        "160\n"
        "Roti\n"
        "15\n"
        "Dal Fry\n"
        "120\n"
        "Samosa\n"
        "20\n"
        "Total\n"
        "315"
    )
    assert _extract_amount(text, text.splitlines()) == Decimal("315")


def test_extracts_restaurant_total_without_clear_total_label():
    text = (
        "Sev Bhaji\n"
        "110\n"
        "Roti\n"
        "45\n"
        "Poha\n"
        "30\n"
        "Chai\n"
        "09\n"
        "245\n"
        "o Rs"
    )
    assert _extract_amount(text, text.splitlines()) is None


def test_prefers_grand_total_over_earlier_sub_total():
    text = (
        "Sub Total\n510.00\nCGST @2.5%\n12.75\nSGST @2.5%\n12.75\n"
        "Round Off\n+0.50\nGRAND TOTAL\nRs\n536.00"
    )
    assert _extract_amount(text, text.splitlines()) == Decimal("536.00")


def test_leaves_slash_misread_amount_blank():
    # OCR read the printed "1230/-" as "12307-".
    text = (
        "Vehicle No: MH32 CP 9655 Km: 75\n12307-\nAmount Rs.\n"
        "One Thousand Two Hundred Thirty only"
    )
    assert _extract_amount(text, text.splitlines()) is None


def test_slash_misread_does_not_fall_through_to_km_reading():
    text = "Km:\n25\n3701-\nAmount Rs.\nThree Hundred Seventy only"
    assert _extract_amount(text, text.splitlines()) is None


def test_accepts_bare_trailing_dash_amount():
    text = "300-\nAmount Rs.\nThree Hundred only"
    assert _extract_amount(text, text.splitlines()) == Decimal("300")
