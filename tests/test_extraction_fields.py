
"""Regression tests for dataset-wide extraction patterns.

The OCR lines follow layouts found in reports/ocr_extractions.csv (fuel pump
slips, parking tickets, restaurant and hotel invoices). They test general
rules; no claim IDs or expected values are hardcoded in the extractor.
"""

import csv
from decimal import Decimal
import subprocess
import sys
from pathlib import Path

import app.extraction as extraction
from app.extraction import combine_passes as extract_receipt_fields_from_passes
from app.extraction import extract_fields_from_lines, gstin_checksum_valid
from app.normalization import normalize_date

ROOT = Path(__file__).resolve().parents[1]

FUEL_SLIP = [
    "BPCL", "LAXMI AUTO FUELS", "Arvi Naka. Wardha", "GSTIN: 27DPAFU4120X1ZM",
    "Receipt No", "003203", "Date: 10/06/26", "Time: 15:29", "Product", "PETROL",
    "Rate (Rs/L): 104.69", "Volume (L) : 2.39", "Amount (Rs): 250.00",
    "Vehicle No : MH32BB1205", "TOTAL", "Rs.", "250.00",
]

PARKING_TICKET = [
    "SITABULDI MULTILEVEL PARKING", "Nagpur Munic1pal Corporation", "Ticket",
    "No: 108873", "Veh No", "MH31FG6627", "Type", "2W", "(Day rate)", "In",
    "13/06/26 11:42", "Out", "13/06/2614:56", "Amount Rs", "30.00",
    "Vehicle parked at owner's risk",
]


def test_fuel_slip_vendor_is_the_station_not_the_oil_company_logo():
    fields = extract_fields_from_lines(FUEL_SLIP)

    assert fields["vendor"] == "LAXMI AUTO FUELS"
    for brand in ("HPCL", "IndianOil", "Bharat Petroleum"):
        assert extract_fields_from_lines([brand] + FUEL_SLIP[1:])["vendor"] == "LAXMI AUTO FUELS"


def test_parking_ticket_uses_its_only_plausible_date():
    # The exit time is glued to the date ("2614:56"), which must not be read
    # as a second date in year 2614.
    assert extract_fields_from_lines(PARKING_TICKET)["receipt_date"] == "2026-06-13"


def test_day_month_name_two_digit_year_dates():
    lines = ["GREEN LEAF RESTAURANT", "TAX INVOICE", "Bill No: A/6248", "Date: 25-Jun-26"]
    assert extract_fields_from_lines(lines)["receipt_date"] == "2026-06-25"
    assert normalize_date("13-Jun-26") == "2026-06-13"


def test_implausible_year_is_left_blank_and_flagged():
    lines = ["CAFE COFFEE CORNER", "TAX INVOICE", "Bill No: A/1774", "Date: 05-08-2826"]
    fields = extract_fields_from_lines(lines)

    assert fields["receipt_date"] == ""
    assert "receipt_date_uncertain_or_missing" in fields["errors"]
    assert normalize_date("05-08-2826") == ""
    # Two-digit years in existing formats still parse as before.
    assert normalize_date("26-06-13") == "2013-06-26"


def test_conflicting_unlabelled_dates_stay_blank():
    lines = ["HIGHWAY KING DHABA", "Particulars", "12/06/26", "1 Thali", "150", "19/06/26"]
    fields = extract_fields_from_lines(lines)

    assert fields["receipt_date"] == ""
    assert "receipt_date_conflicting_candidates" in fields["errors"]


def test_labelled_date_is_kept_when_another_date_appears_unlabelled():
    lines = ["VIDARBHA EXPRESS COURIER", "AWB No : VX11449697",
             "Date : 22/06/2026 13:30", "Printed 25/06/2026"]
    fields = extract_fields_from_lines(lines)

    assert fields["receipt_date"] == "2026-06-22"
    assert not any("date" in error for error in fields["errors"])


def test_labelled_invoice_date_still_wins_over_check_in_and_out():
    lines = [
        "HOTEL GULMOHAR EXECUTIVE", "TAX INVOICE", "Invoice No: HGE/26-27/7505",
        "Check-in: 14 Jun 2026 13:30", "Invoice Date: 16 Jun 2026",
        "Check-out: 16 Jun 2026 10:15",
    ]
    assert extract_fields_from_lines(lines)["receipt_date"] == "2026-06-16"


def test_gstin_with_letter_o_read_as_zero_is_repaired_when_checksum_validates():
    fields = extract_fields_from_lines(["HOTEL PRADEEP PURE VEG", "GSTIN: 270DUFJ1789K3ZU"])

    assert fields["gstin"] == "27ODUFJ1789K3ZU"
    assert gstin_checksum_valid(fields["gstin"])


def test_valid_gstin_is_kept_unchanged():
    assert extract_fields_from_lines(FUEL_SLIP)["gstin"] == "27DPAFU4120X1ZM"


def test_gstin_failing_its_checksum_is_left_blank_and_flagged():
    fields = extract_fields_from_lines(["SPEEDLINK COURIERS", "GSTIN: 27WJXCW9975D1ZJ"])

    assert fields["gstin"] == ""
    assert "gstin_checksum_failed" in fields["errors"]


def test_gstin_checksum_accepts_published_examples_and_rejects_one_char_changes():
    for gstin in ("27AAPFU0939F1ZV", "29AAGCB7383J1Z4", "27DPAFU4120X1ZM"):
        assert gstin_checksum_valid(gstin), gstin
    assert not gstin_checksum_valid("27AAPFU0939F1ZW")  # wrong check character
    assert not gstin_checksum_valid("27AAPFU0939F1Z")   # too short


def test_gstin_state_code_must_be_valid():
    # Whatever the check character, an impossible state code never validates.
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert not any(gstin_checksum_valid("00DPAFU4120X1Z" + c) for c in alphabet)
    assert not any(gstin_checksum_valid("45DPAFU4120X1Z" + c) for c in alphabet)
    assert sum(gstin_checksum_valid("27DPAFU4120X1Z" + c) for c in alphabet) == 1


def test_gstin_repairs_common_ocr_confusions():
    expected = "27DPAFU4120X1ZM"
    for ocr_text in ("27DPAFU4120X12M",   # Z read as 2
                     "27DPAFU412OX1ZM",   # 0 read as O in a digit position
                     "27DPAFU4I20X1ZM"):  # 1 read as I in a digit position
        assert extract_fields_from_lines(["GSTIN: " + ocr_text])["gstin"] == expected


def test_gstin_is_not_guessed_when_evidence_is_insufficient():
    # A letter D read as 0 cannot be told apart from O, so no repair validates.
    fields = extract_fields_from_lines(["LAXMI AUTO FUELS", "GSTIN: 270PAFU4120X1ZM"])
    assert fields["gstin"] == ""
    # Ordinary 15-character text is never turned into a GSTIN.
    assert extract_fields_from_lines(["THANKYOUVISITAG"])["gstin"] == ""


def test_live_extraction_uses_the_shared_field_rules(monkeypatch, tmp_path):
    class FakeOCR:
        def predict(self, _):
            return [{"rec_texts": FUEL_SLIP}]

    monkeypatch.setattr(extraction, "_get_ocr", lambda: FakeOCR())
    image = tmp_path / "receipt.jpg"
    image.write_bytes(b"not read by the fake OCR")

    result = extraction.extract_receipt_fields(image)

    assert result["raw_text"] == "\n".join(FUEL_SLIP)
    assert result["readable"] is True
    assert result["vendor"] == "LAXMI AUTO FUELS"
    assert result["receipt_date"] == "2026-06-10"


def test_reextraction_script_refuses_to_overwrite_its_input(tmp_path):
    source = tmp_path / "ocr.csv"
    with source.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["image_filename", "raw_text"])
        writer.writeheader()
        writer.writerow({"image_filename": "a.jpg", "raw_text": "\n".join(FUEL_SLIP)})

    script = str(ROOT / "scripts" / "reextract_from_raw_text.py")
    same = subprocess.run([sys.executable, script, "--input", str(source), "--output", str(source)],
                          capture_output=True, text=True)
    assert same.returncode != 0

    output = tmp_path / "v2.csv"
    ok = subprocess.run([sys.executable, script, "--input", str(source), "--output", str(output)],
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    with output.open(newline="", encoding="utf-8-sig") as file:
        row = next(csv.DictReader(file))
    assert row["vendor"] == "LAXMI AUTO FUELS" and row["receipt_date"] == "2026-06-10"


CAB_RECEIPT = [
    "MAA DURGA CAB SERVICE", "Near Bus Stand, Chandrapur | Mob: 94221 08812",
    "Date: 14/6/26", "No. 8219", "From: Railway Stn", "To: Dhantoli",
    "Vehicle No: MH32 CP 9655 Km: 75", "12307-", "Amount Rs.",
    "One Thousand Two Hundred Thirty only", "Rupees (in words):",
]


def test_slash_misread_total_is_resolved_by_the_bills_amount_in_words():
    # '1230/-' read as '12307-'; the words on the same bill settle it.
    fields = extract_fields_from_lines(CAB_RECEIPT)

    assert str(fields["total_amount"]) == "1230.00"
    assert str(fields["amount_in_words_value"]) == "1230"
    assert fields["amount_in_words"] == "One Thousand Two Hundred Thirty only"
    assert "amount_in_words_differs_from_figure" not in fields["notes"]


def test_slash_misread_total_stays_blank_without_agreeing_words():
    no_words = [line for line in CAB_RECEIPT if "Thousand" not in line]
    assert extract_fields_from_lines(no_words)["total_amount"] is None

    # Words that match neither reading (1550 / 15507 vs 550) are not used.
    contradicted = ["No. 3741", "15507-", "Amount Rs.", "Rupees (in words): Five Hundred Fifty only"]
    assert extract_fields_from_lines(contradicted)["total_amount"] is None


def test_clear_figure_contradicting_words_is_flagged_not_corrected():
    lines = ["No. 3741", "Amount Rs. 1550/-", "Rupees (in words): Five Hundred Fifty only"]
    fields = extract_fields_from_lines(lines)

    assert fields["total_amount"] == Decimal("1550")
    assert "amount_in_words_differs_from_figure" in fields["notes"]


def test_total_label_split_over_lines_below_the_amount():
    lines = ["Sub Total", "600.00", "Round Off", "630.00", "GRAND", "TOTAL", "Rs", "-2-pax"]
    assert str(extract_fields_from_lines(lines)["total_amount"]) == "630.00"


def test_misread_receipt_and_awb_labels():
    assert extract_fields_from_lines(["OM SAI FUEL POINT", "Redeipt No : 004185"])["receipt_number"] == "004185"
    assert extract_fields_from_lines(["SPEEDLINK COURIERS", "AMB No : SL73161147"])["receipt_number"] == "SL73161147"


def test_time_glued_to_four_digit_year():
    lines = ["SPEEDLINK COURIERS", "AWB No : SL26816175", "Date", ":24-06-202616:24"]
    assert extract_fields_from_lines(lines)["receipt_date"] == "2026-06-24"


def test_date_with_slashes_read_as_ones_needs_a_single_reading():
    one = extract_fields_from_lines(["ROYAL TRAVELS", "No. 8501", "Date:25/712026"])
    assert one["receipt_date"] == "2026-07-25"
    assert "receipt_date_read_with_misread_separators" in one["notes"]

    both = extract_fields_from_lines(["SHREE GANESH TOURS", "Date:", "171712026"])
    assert both["receipt_date"] == "2026-07-17"

    # '111112026' fits two dates (1/11/2026 and 11/1/2026): left blank.
    ambiguous = extract_fields_from_lines(["SHREE GANESH TOURS", "Date: 111112026"])
    assert ambiguous["receipt_date"] == ""


def test_route_and_distance_only_from_the_same_line():
    fields = extract_fields_from_lines(CAB_RECEIPT)
    assert (fields["route_from"], fields["route_to"], fields["km"]) == ("Railway Stn", "Dhantoli", "75")

    scattered = extract_fields_from_lines(["From:", "To:", "Butibori", "Km:", "73"])
    assert (scattered["route_to"], scattered["km"]) == ("", "")


def test_enhanced_pass_fills_blanks_and_never_overrides():
    primary = ["ROYAL TRAVELS", "No. 8400", "Date: /7/26", "Amount Rs.290/-"]
    enhanced = ["ROYAL TRAVELS", "No. 9999", "Date: 1/7/26", "Amount Rs.990/-"]

    fields = extract_receipt_fields_from_passes(primary, enhanced)

    assert fields["receipt_date"] == "2026-07-01"
    assert fields["receipt_number"] == "8400"
    assert fields["total_amount"] == Decimal("290")
    assert fields["filled_by_enhanced_pass"] == ["receipt_date"]
    assert "receipt_date_uncertain_or_missing" not in fields["errors"]


def test_handwritten_figure_split_by_ocr_is_left_blank():
    # '1,940/-' read as '940/-' plus a stray '1' after the label: neither
    # 1 nor 940 is the bill's figure, even though the words say 940.
    lines = ["MAA DURGA CAB SERVICE", "No. 8290", "Km:", "940/-", "Amount Rs. 1",
             "Nine Hundred Forty only", "Rupees (in words):"]
    fields = extract_fields_from_lines(lines)

    assert fields["total_amount"] is None
    assert fields["amount_in_words_value"] == Decimal("940")
