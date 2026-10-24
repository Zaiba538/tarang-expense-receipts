"""Rule-based expense policy checks for Tarang Pharma Distribution."""

from __future__ import annotations

from typing import Any

from app.integrity_checks import classify_vehicle
from app.normalization import normalize_amount, normalize_text


FOOD_LIMIT = 2500.0
LODGING_LIMITS = {
    "M1": 3000.0,
    "M2": 3000.0,
    "M3": 4500.0,
}


def _truthy(value: Any) -> bool:
    """Interpret common CSV boolean values."""
    return normalize_text(value).lower() in {
        "true", "yes", "y", "1", "available", "present"
    }


def evaluate_policy(
    claim: dict[str, Any],
    receipt: dict[str, Any] | None = None,
    employee: dict[str, Any] | None = None,
    receipt_available: bool = True,
    duplicate_detected: bool = False,
    vehicle_registry: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Evaluate a claim against policy rules.

    vehicle_registry maps normalized plate numbers to employee IDs and is
    used to identify a fuel bill showing a colleague's vehicle.
    """
    receipt = receipt or {}
    employee = employee or {}

    category = normalize_text(claim.get("category")).lower()
    vendor = normalize_text(receipt.get("vendor") or claim.get("vendor"))
    amount = normalize_amount(
        receipt.get("total_amount", claim.get("amount_claimed"))
    )
    claim_amount = normalize_amount(claim.get("amount_claimed"))
    grade = normalize_text(employee.get("grade")).upper()

    reasons: list[str] = []
    hard_flags: list[str] = []
    vehicle_status = ""

    if not receipt_available or not _truthy(receipt.get("readable", True)):
        reasons.append(
            "Receipt image unavailable or unreadable; request a readable copy."
        )

    if amount is None:
        reasons.append("Receipt amount is missing or unreadable.")
    elif claim_amount is not None and abs(amount - claim_amount) > 10:
        reasons.append("Claimed amount differs from receipt by more than ₹10.")

    if duplicate_detected:
        hard_flags.append(
            "Possible duplicate claim or receipt; investigate before payment."
        )

    if category == "fuel":
        expected_vehicle = "".join(
            normalize_text(employee.get("vehicle_no")).upper().split()
        )
        if not expected_vehicle:
            reasons.append(
                "Employee vehicle details are unavailable; verify fuel eligibility."
            )
        else:
            vehicle = classify_vehicle(
                receipt.get("vehicle_no"),
                expected_vehicle,
                vehicle_registry,
                normalize_text(employee.get("emp_id")),
            )
            vehicle_status = vehicle["status"]
            # Only a reliably read plate is a hard flag; uncertain OCR is not.
            if vehicle["status"] in {"other_employee", "mismatch"}:
                hard_flags.append(vehicle["message"])
            elif vehicle["status"] in {"missing", "uncertain"}:
                reasons.append(vehicle["message"])

        if not _truthy(claim.get("field_day")):
            reasons.append(
                "Confirm the fuel expense relates to an eligible field day."
            )

    elif category == "food":
        if amount is not None and amount > FOOD_LIMIT:
            reasons.append("Food bill exceeds ₹2,500; check for prior approval.")
        if not vendor:
            reasons.append(
                "Food vendor could not be established from the receipt."
            )

    elif category == "lodging":
        limit = LODGING_LIMITS.get(grade)
        if limit is None:
            reasons.append(
                "Employee grade is unavailable; verify the lodging limit."
            )
        elif amount is not None and amount > limit:
            reasons.append(
                f"Lodging amount exceeds the ₹{limit:,.0f} grade limit; "
                "verify the amount before GST."
            )

        if not _truthy(receipt.get("gst_tax_invoice")):
            reasons.append(
                "Confirm the hotel bill is a GST tax invoice in the employee's name."
            )

        if not _truthy(claim.get("outstation_night")):
            reasons.append(
                "Confirm the lodging was for an eligible outstation night."
            )

    elif category == "local travel":
        if not _truthy(receipt.get("driver_receipt")):
            reasons.append("Local travel requires a readable driver receipt.")

    elif category == "courier":
        if not vendor:
            reasons.append(
                "Courier vendor is missing or unreadable; verify the receipt."
            )

    elif category == "parking":
        pass

    else:
        reasons.append(
            "Expense category is unknown; manual policy review is required."
        )

    if hard_flags:
        decision = "review"
        reasons.extend(hard_flags)
    elif reasons:
        decision = "review"
    else:
        decision = "approve"

    return {
        "decision": decision,
        "reasons": list(dict.fromkeys(reasons)),
        "hard_flags": hard_flags,
        "vehicle_status": vehicle_status,
        "vendor": vendor,
        "amount": float(amount) if amount is not None else None,
    }
