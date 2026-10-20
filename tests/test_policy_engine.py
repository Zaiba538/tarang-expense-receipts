from app.policy_engine import evaluate_policy


def make_claim(category, amount=500, **extra):
    return {
        "claim_id": "CLM-TEST-001",
        "category": category,
        "vendor": "Test Vendor",
        "amount_claimed": amount,
        **extra,
    }


def make_receipt(amount=500, **extra):
    return {
        "vendor": "Test Vendor",
        "receipt_date": "2026-07-18",
        "receipt_number": "TEST-001",
        "total_amount": amount,
        "readable": True,
        **extra,
    }


def make_employee(**extra):
    return {
        "emp_id": "EMP-001",
        "grade": "M1",
        "vehicle_no": "MH01AB1234",
        **extra,
    }


def test_parking_with_matching_amount_is_approved():
    result = evaluate_policy(make_claim("parking"), make_receipt(), make_employee())
    assert result["decision"] == "approve"


def test_food_within_limit_is_approved():
    result = evaluate_policy(make_claim("food", 2500), make_receipt(2500), make_employee())
    assert result["decision"] == "approve"


def test_food_above_limit_requires_review():
    result = evaluate_policy(make_claim("food", 2600), make_receipt(2600), make_employee())
    assert result["decision"] == "review"
    assert any("prior approval" in reason for reason in result["reasons"])


def test_fuel_with_matching_vehicle_and_field_day_is_approved():
    result = evaluate_policy(
        make_claim("fuel", 500, field_day=True),
        make_receipt(500, vehicle_no="MH01AB1234"),
        make_employee(),
    )
    assert result["decision"] == "approve"


def test_fuel_with_mismatched_vehicle_requires_review():
    result = evaluate_policy(
        make_claim("fuel", 500, field_day=True),
        make_receipt(500, vehicle_no="MH02XY9999"),
        make_employee(),
    )
    assert result["decision"] == "review"
    assert result["hard_flags"]


def test_fuel_without_field_day_confirmation_requires_review():
    result = evaluate_policy(
        make_claim("fuel", 500, field_day=False),
        make_receipt(500, vehicle_no="MH01AB1234"),
        make_employee(),
    )
    assert result["decision"] == "review"


def test_lodging_within_limit_and_evidence_is_approved():
    result = evaluate_policy(
        make_claim("lodging", 2500, outstation_night=True),
        make_receipt(2500, gst_tax_invoice=True),
        make_employee(grade="M1"),
    )
    assert result["decision"] == "approve"


def test_lodging_above_grade_limit_requires_review():
    result = evaluate_policy(
        make_claim("lodging", 3200, outstation_night=True),
        make_receipt(3200, gst_tax_invoice=True),
        make_employee(grade="M1"),
    )
    assert result["decision"] == "review"


def test_lodging_without_required_evidence_requires_review():
    result = evaluate_policy(
        make_claim("lodging", 2500),
        make_receipt(2500),
        make_employee(grade="M1"),
    )
    assert result["decision"] == "review"


def test_local_travel_without_driver_receipt_requires_review():
    result = evaluate_policy(
        make_claim("local travel", 300),
        make_receipt(300),
        make_employee(),
    )
    assert result["decision"] == "review"


def test_local_travel_with_driver_receipt_is_approved():
    result = evaluate_policy(
        make_claim("local travel", 300),
        make_receipt(300, driver_receipt=True),
        make_employee(),
    )
    assert result["decision"] == "approve"


def test_courier_with_vendor_and_matching_amount_is_approved():
    result = evaluate_policy(
        make_claim("courier", 150),
        make_receipt(150, vendor="SPEEDLINK COURIERS"),
        make_employee(),
    )
    assert result["decision"] == "approve"


def test_missing_receipt_image_requires_review():
    result = evaluate_policy(
        make_claim("parking"),
        make_receipt(),
        make_employee(),
        receipt_available=False,
    )
    assert result["decision"] == "review"
    assert any("request a readable copy" in reason for reason in result["reasons"])


def test_amount_mismatch_over_ten_rupees_requires_review():
    result = evaluate_policy(
        make_claim("parking", 500),
        make_receipt(511),
        make_employee(),
    )
    assert result["decision"] == "review"


def test_duplicate_claim_requires_review():
    result = evaluate_policy(
        make_claim("parking"),
        make_receipt(),
        make_employee(),
        duplicate_detected=True,
    )
    assert result["decision"] == "review"
    assert result["hard_flags"]


def test_unknown_category_requires_review():
    result = evaluate_policy(
        make_claim("unknown"),
        make_receipt(),
        make_employee(),
    )
    assert result["decision"] == "review"
