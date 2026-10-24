
from scripts.generate_predictions import submission_vendor


def test_vendor_is_taken_from_the_bill():
    assert submission_vendor(
        {"vendor": "HOTEL RAJDHANI DHABA", "_receipt_available": True}
    ) == "HOTEL RAJDHANI DHABA"


def test_unread_vendor_stays_blank():
    # The rep-typed claim vendor must never stand in for the printed vendor.
    assert submission_vendor({"vendor": "", "_receipt_available": True}) == ""


def test_vendor_blank_without_a_matched_receipt_image():
    # Training clerk fields can sit in the receipt dict for duplicate checks;
    # they are not evidence from the photo.
    assert submission_vendor(
        {"vendor": "Clerk Typed Vendor", "_receipt_available": False}
    ) == ""
