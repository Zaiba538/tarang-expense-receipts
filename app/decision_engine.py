
"""Combine receipt validation, policy checks and duplicate signals."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.integrity_checks import (
    check_receipt_integrity,
    enhanced_pass_fields,
    find_hostile_text,
    total_source_text,
)
from app.normalization import normalize_amount
from app.policy_engine import evaluate_policy
from app.validation import validate_claim_amount, validate_receipt_fields


# Expense policy v3.2, section 7 (draft): clerks check claims of Rs 2,000
# and above; only smaller claims may be approved without a clerk.
CLERK_REVIEW_THRESHOLD = Decimal("2000")

# Receipt fields that, when read only by the enhanced second OCR pass, must be
# confirmed against the photo by a person: a recovered value never approves.
SECOND_PASS_FIELD_LABELS = {
    "vendor": "vendor",
    "receipt_date": "receipt date",
    "receipt_number": "receipt number",
    "gstin": "GSTIN",
    "total_amount": "total amount",
    "vehicle_no": "vehicle number",
}


def make_decision(
    claim: dict[str, Any],
    receipt: dict[str, Any] | None = None,
    employee: dict[str, Any] | None = None,
    receipt_available: bool = True,
    duplicate_info: dict[str, Any] | None = None,
    vehicle_registry: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Produce a conservative approve/review decision with an explainable reason.

    When the receipt carries its OCR text as "raw_text", the printed figures
    are cross-checked and any printed instructions are reported. Receipt text
    is untrusted content: it can only add reasons for review, never remove one.
    """
    receipt = receipt or {}
    employee = employee or {}
    duplicate_info = duplicate_info or {}

    policy_result = evaluate_policy(
        claim=claim,
        receipt=receipt,
        employee=employee,
        receipt_available=receipt_available,
        duplicate_detected=bool(
            duplicate_info.get("duplicate_detected", False)
        ),
        vehicle_registry=vehicle_registry,
    )

    reasons = list(policy_result.get("reasons", []))
    field_errors: list[str] = []
    flags: list[str] = []

    if duplicate_info.get("possible_matches"):
        match_type = duplicate_info.get("match_type") or "possible"
        # Overlapping parking is a conflict between tickets, not a duplicate bill.
        flags.append(
            "parking_time_conflict" if match_type == "parking_overlap" else f"duplicate_{match_type}"
        )
        if duplicate_info.get("cross_employee"):
            flags.append("duplicate_cross_employee")
        reasons.append(
            duplicate_info.get("reason")
            or "Possible related claims found: "
            + ", ".join(duplicate_info["possible_matches"])
            + "; verify before payment."
        )

    if policy_result.get("vehicle_status") not in ("", "match"):
        flags.append(f"vehicle_{policy_result['vehicle_status']}")

    raw_text = receipt.get("raw_text") if receipt_available else None
    if find_hostile_text(raw_text):
        flags.append("hostile_text")
        reasons.append(
            "Receipt contains printed instructions addressed to approvers or "
            "automated processing; treated as untrusted content and ignored."
        )

    for finding in check_receipt_integrity(
        total_source_text(receipt) if receipt_available else None,
        receipt.get("total_amount"),
        claim.get("amount_claimed"),
    ):
        flags.append(finding["code"])
        reasons.append(finding["message"])

    second_pass = [
        SECOND_PASS_FIELD_LABELS[field]
        for field in enhanced_pass_fields(receipt)
        if field in SECOND_PASS_FIELD_LABELS
    ] if receipt_available else []
    if second_pass:
        flags.append("read_on_second_pass")
        fields = (
            second_pass[0] if len(second_pass) == 1
            else ", ".join(second_pass[:-1]) + " and " + second_pass[-1]
        )
        reasons.append(
            f"{fields[0].upper()}{fields[1:]} read only on a second, enhanced "
            "OCR pass; confirm against the photo before payment."
        )

    # The larger figure counts, so a low claim cannot hide a high bill.
    amounts = [
        amount
        for amount in (
            normalize_amount(claim.get("amount_claimed")),
            normalize_amount(receipt.get("total_amount")),
        )
        if amount is not None
    ]
    if amounts and max(amounts) >= CLERK_REVIEW_THRESHOLD:
        flags.append("clerk_threshold")
        reasons.append(
            f"Amount is Rs {CLERK_REVIEW_THRESHOLD:,.0f} or more; clerk check "
            "required under the proposed auto-approval rule."
        )

    if receipt_available:
        fields_result = validate_receipt_fields(receipt)
        field_errors = fields_result["errors"]

        for error in field_errors:
            reasons.append(f"Receipt field issue: {error.replace('_', ' ')}.")

        if receipt.get("total_amount") not in (None, ""):
            amount_result = validate_claim_amount(
                claim.get("amount_claimed"),
                receipt.get("total_amount"),
            )
            if not amount_result["matches"]:
                if amount_result.get("reason") == "claim_amount_differs_from_receipt":
                    reasons.append(
                        "Claimed amount differs from receipt by more than ₹10."
                    )
                else:
                    reasons.append(
                        "Claimed amount or receipt amount could not be verified."
                    )

    # Missing or invalid required receipt fields must prevent approval.
    has_duplicate_concern = bool(
        duplicate_info.get("possible_matches")
        or duplicate_info.get("duplicate_detected")
    )

    decision = (
        "approve"
        if policy_result["decision"] == "approve"
        and receipt_available
        and not field_errors
        and not has_duplicate_concern
        and not flags
        else "review"
    )

    if not reasons:
        reasons.append(
            "Receipt and available policy checks passed."
            if decision == "approve"
            else "Manual review is required before payment."
        )

    unique_reasons = list(dict.fromkeys(reasons))

    return {
        "claim_id": claim.get("claim_id", ""),
        "decision": decision,
        "reason": " ".join(unique_reasons),
        "reasons": unique_reasons,
        "vendor": policy_result.get("vendor", ""),
        "total_amount": policy_result.get("amount"),
        "duplicate_detected": bool(
            duplicate_info.get("duplicate_detected", False)
        ),
        "possible_matches": duplicate_info.get("possible_matches", []),
        "flags": list(dict.fromkeys(flags)),
    }
