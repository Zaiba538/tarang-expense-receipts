
from app.extraction import _extract_receipt_number


def test_extracts_labelled_invoice_number():
    text = "TAX INVOICE\nInvoice No: HCP/26-27/4594"
    assert _extract_receipt_number(text) == "HCP/26-27/4594"


def test_extracts_bare_no_on_cab_receipt():
    text = "Mob: 94221 08812\nDate: 14/6/26\nNo. 8219\nVehicle No: MH32 CP 9655"
    assert _extract_receipt_number(text) == "8219"


def test_extracts_bare_no_without_space():
    assert _extract_receipt_number("MAA DURGA CAB SERVICE\nNo.8235") == "8235"


def test_extracts_bill_number_with_ocr_misread_label():
    assert _extract_receipt_number("TAX INVOICE\nB1ll No: A/6178") == "A/6178"
    assert _extract_receipt_number("TAX INVOICE\nB111 No: 6191") == "6191"
    assert _extract_receipt_number("Family Section\nBil No. 3295") == "3295"


def test_extracts_number_after_full_width_colon():
    text = "Badnera Road. Amravati\nReceipt No\n：001351"
    assert _extract_receipt_number(text) == "001351"


def test_skips_label_word_and_date_before_number():
    assert _extract_receipt_number("Bill No.\nDate_20-6-2026\n6896") == "6896"
    assert _extract_receipt_number("NO.\n26-6-2026\n8381") == "8381"


def test_does_not_use_vehicle_number_as_receipt_number():
    assert _extract_receipt_number("Vehicle No: MH31 CP 5099\nKm: 31") == ""
