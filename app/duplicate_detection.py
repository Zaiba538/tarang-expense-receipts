
"""Duplicate receipt and claim detection for Tarang Pharma Distribution."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.normalization import (
    normalize_amount,
    normalize_date,
    normalize_gstin,
    normalize_receipt_number,
    normalize_text,
)


def _normalized_vendor(value: object) -> str:
    """Normalize vendor text for duplicate comparisons."""
    return normalize_text(value).casefold()


def detect_duplicates(
    claims: list[dict[str, Any]],
    receipts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Flag possible duplicate claims using receipt evidence.

    Returns a result keyed by claim_id. A matching vendor and amount alone
    is not enough to establish a duplicate. Missing receipt identifiers are
    not fabricated, and potential matches require manual review.
    """
    receipts = receipts or {}
    prepared: list[dict[str, Any]] = []

    for claim in claims:
        claim_id = normalize_text(claim.get("claim_id"))
        receipt = receipts.get(claim_id, {})
        amount = normalize_amount(
            receipt.get("total_amount", claim.get("amount_claimed"))
        )

        prepared.append(
            {
                "claim_id": claim_id,
                "vendor": _normalized_vendor(
                    receipt.get("vendor") or claim.get("vendor")
                ),
                "date": normalize_date(
                    receipt.get("receipt_date") or claim.get("expense_date")
                ),
                "number": normalize_receipt_number(
                    receipt.get("receipt_number")
                ),
                "gstin": normalize_gstin(receipt.get("gstin")),
                "amount": amount,
            }
        )

    # Stronger evidence: the same receipt number and vendor.
    by_receipt: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in prepared:
        if item["number"] and item["vendor"]:
            by_receipt[(item["vendor"], item["number"])].append(item)

    results: dict[str, dict[str, Any]] = {
        item["claim_id"]: {
            "duplicate_detected": False,
            "possible_matches": [],
            "reason": "",
        }
        for item in prepared
        if item["claim_id"]
    }

    for group in by_receipt.values():
        if len(group) > 1:
            ids = [item["claim_id"] for item in group]
            for item in group:
                results[item["claim_id"]]["duplicate_detected"] = True
                results[item["claim_id"]]["possible_matches"] = [
                    other_id for other_id in ids
                    if other_id != item["claim_id"]
                ]
                results[item["claim_id"]]["reason"] = (
                    "Same vendor and receipt number appear in multiple claims; investigate."
                )

    # Weaker evidence is surfaced for review, not treated as a confirmed duplicate.
    for index, item in enumerate(prepared):
        if not item["claim_id"] or results[item["claim_id"]]["duplicate_detected"]:
            continue

        for other in prepared[index + 1:]:
            if not other["claim_id"] or other["claim_id"] == item["claim_id"]:
                continue
            if item["vendor"] != other["vendor"] or not item["vendor"]:
                continue
            if item["amount"] is None or other["amount"] is None:
                continue
            if item["amount"] != other["amount"]:
                continue
            if item["date"] and other["date"] and item["date"] != other["date"]:
                continue

            results[item["claim_id"]]["possible_matches"].append(other["claim_id"])
            results[other["claim_id"]]["possible_matches"].append(item["claim_id"])

            if not results[item["claim_id"]]["reason"]:
                results[item["claim_id"]]["reason"] = (
                    "Same vendor, amount and compatible date; verify whether receipts are duplicated."
                )
            if not results[other["claim_id"]]["reason"]:
                results[other["claim_id"]]["reason"] = (
                    "Same vendor, amount and compatible date; verify whether receipts are duplicated."
                )

    return results
