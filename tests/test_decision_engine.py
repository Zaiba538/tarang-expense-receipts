from app.decision_engine import make_decision


def make_claim(category="parking", amount=500):
    return {
        "claim_id": "CLM-TEST-001",
        "category": category,
        "vendor": "Test Vendor",
        "amount_claimed": amount,
    }


def make_receipt(amount=500, **extra):
    return {
        "vendor": "Test Vendor",
        "receipt_date": "2026-07-18",
        "receipt_number": "TEST-001",
        "gstin": "",
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


def test_valid_parking_claim_is_approved():
    result = make_decision(
        make_claim(),
        make_receipt(),
        make_employee(),
    )
    assert result["decision"] == "approve"
    assert result["claim_id"] == "CLM-TEST-001"


def test_missing_receipt_image_requires_review():
    result = make_decision(
        make_claim(),
        make_receipt(),
        make_employee(),
        receipt_available=False,
    )
    assert result["decision"] == "review"


def test_missing_receipt_date_requires_review():
    receipt = make_receipt()
    receipt["receipt_date"] = ""

    result = make_decision(make_claim(), receipt, make_employee())

    assert result["decision"] == "review"
    assert "receipt date missing" in result["reason"].lower()


def test_missing_receipt_number_requires_review():
    receipt = make_receipt()
    receipt["receipt_number"] = ""

    result = make_decision(make_claim(), receipt, make_employee())

    assert result["decision"] == "review"


def test_missing_receipt_amount_requires_review():
    receipt = make_receipt()
    receipt["total_amount"] = ""

    result = make_decision(make_claim(), receipt, make_employee())

    assert result["decision"] == "review"


def test_amount_mismatch_requires_review():
    result = make_decision(
        make_claim(amount=500),
        make_receipt(amount=520),
        make_employee(),
    )

    assert result["decision"] == "review"
    assert "differs from receipt" in result["reason"].lower()


def test_duplicate_detected_requires_review():
    result = make_decision(
        make_claim(),
        make_receipt(),
        make_employee(),
        duplicate_info={"duplicate_detected": True},
    )

    assert result["decision"] == "review"
    assert result["duplicate_detected"] is True


def test_possible_duplicate_match_requires_review():
    result = make_decision(
        make_claim(),
        make_receipt(),
        make_employee(),
        duplicate_info={
            "duplicate_detected": False,
            "possible_matches": ["CLM-TEST-002"],
        },
    )

    assert result["decision"] == "review"
    assert "CLM-TEST-002" in result["reason"]


def test_food_above_limit_requires_review():
    result = make_decision(
        make_claim(category="food", amount=2600),
        make_receipt(amount=2600),
        make_employee(),
    )

    assert result["decision"] == "review"
    assert "prior approval" in result["reason"].lower()


def test_fuel_vehicle_mismatch_requires_review():
    result = make_decision(
        make_claim(category="fuel"),
        make_receipt(vehicle_no="MH02XY9999"),
        make_employee(),
    )

    assert result["decision"] == "review"


def test_result_contains_explanation_and_receipt_fields():
    result = make_decision(
        make_claim(),
        make_receipt(),
        make_employee(),
    )

    assert result["claim_id"] == "CLM-TEST-001"
    assert result["vendor"] == "Test Vendor"
    assert result["total_amount"] == 500.0
    assert isinstance(result["reason"], str)
    assert result["reason"].strip()
    assert isinstance(result["reasons"], list)
