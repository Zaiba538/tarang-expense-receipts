
"""Combine receipt validation, policy checks and duplicate signals."""

from __future__ import annotations

from typing import Any

from app.policy_engine import evaluate_policy
from app.validation import validate_claim_amount, validate_receipt_fields


def make_decision(
    claim: dict[str, Any],
    receipt: dict[str, Any] | None = None,
    employee: dict[str, Any] | None = None,
    receipt_available: bool = True,
    duplicate_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a conservative approve/review decision with an explainable reason."""
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
    )

    reasons = list(policy_result.get("reasons", []))
    field_errors: list[str] = []

    if duplicate_info.get("possible_matches"):
        reasons.append(
            "Possible related claims found: "
            + ", ".join(duplicate_info["possible_matches"])
            + "; verify before payment."
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
    }
