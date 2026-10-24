
"""UI regression tests for ui/streamlit_app.py, with OCR stubbed out."""

import io
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

import app.extraction

APP_FILE = str(Path(__file__).resolve().parents[1] / "ui" / "streamlit_app.py")

RECEIPTS = {
    "first.png": {
        "vendor": "ANNAPURNA DINING HALL", "receipt_date": "2026-07-16",
        "receipt_number": "A/1608", "gstin": "", "total_amount": "567.00",
        "vehicle_no": "", "raw_text": "", "readable": True, "errors": [],
    },
    "second.png": {
        "vendor": "SPICE ROUTE KITCHEN", "receipt_date": "2026-07-22",
        "receipt_number": "6423", "gstin": "", "total_amount": "1200.00",
        "vehicle_no": "", "raw_text": "", "readable": True, "errors": [],
    },
}


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def text_input(at: AppTest, label: str):
    return next(widget for widget in at.text_input if widget.label == label)


def extract(at: AppTest, filename: str, claim_id: str, amount: str) -> None:
    at.file_uploader[0].upload(filename, png_bytes(), "image/png")
    at.run()
    text_input(at, "Claim ID").set_value(claim_id)
    text_input(at, "Employee ID").set_value("TPD-0452")
    text_input(at, "Claimed amount (₹)").set_value(amount)
    next(b for b in at.button if b.label == "Extract receipt fields").click()
    at.run()


@pytest.fixture
def fake_ocr(monkeypatch):
    uploaded = []

    def fake_extract(path):
        # The UI writes the upload to a temp file; map it back by upload order.
        return dict(RECEIPTS[uploaded.pop(0)])

    monkeypatch.setattr(app.extraction, "extract_receipt_fields", fake_extract)
    return uploaded


def test_second_extraction_replaces_the_editable_receipt_fields(fake_ocr):
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.run()

    fake_ocr.append("first.png")
    extract(at, "first.png", "CLM-31105", "567")
    assert not at.exception
    assert at.text_input(key="edit_vendor").value == "ANNAPURNA DINING HALL"
    assert at.text_input(key="edit_total_amount").value == "567.00"

    fake_ocr.append("second.png")
    extract(at, "second.png", "CLM-31192", "1200")
    assert not at.exception
    assert at.text_input(key="edit_vendor").value == "SPICE ROUTE KITCHEN"
    assert at.text_input(key="edit_receipt_number").value == "6423"
    assert at.text_input(key="edit_total_amount").value == "1200.00"


def test_reviewer_edits_survive_reruns_until_the_next_extraction(fake_ocr):
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.run()

    fake_ocr.append("first.png")
    extract(at, "first.png", "CLM-31105", "567")
    at.text_input(key="edit_vendor").set_value("Corrected Vendor")
    at.run()
    assert at.text_input(key="edit_vendor").value == "Corrected Vendor"


def solid_png(colour: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def editable_field_keys(at: AppTest) -> set[str]:
    return {widget.key for widget in at.text_input if widget.key and widget.key.startswith("edit_")}


def test_new_upload_clears_the_previous_receipt_before_extraction(fake_ocr):
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.run()
    fake_ocr.append("first.png")
    extract(at, "first.png", "CLM-31105", "567")
    assert at.text_input(key="edit_vendor").value == "ANNAPURNA DINING HALL"

    # A different photo (different bytes), not yet extracted: nothing from the
    # first receipt may remain on screen.
    at.file_uploader[0].upload("second.png", solid_png("black"), "image/png")
    at.run()
    assert not at.exception
    assert editable_field_keys(at) == set()
    assert "receipt" not in at.session_state and "last_result" not in at.session_state

    # Extracting it shows the new receipt without a page refresh.
    fake_ocr.append("second.png")
    next(b for b in at.button if b.label == "Extract receipt fields").click()
    at.run()
    assert at.text_input(key="edit_vendor").value == "SPICE ROUTE KITCHEN"


def test_reuploading_the_same_image_keeps_the_extracted_fields(fake_ocr):
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.run()
    fake_ocr.append("first.png")
    extract(at, "first.png", "CLM-31105", "567")

    at.file_uploader[0].upload("renamed.png", png_bytes(), "image/png")
    at.run()
    assert at.text_input(key="edit_vendor").value == "ANNAPURNA DINING HALL"
