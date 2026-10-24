
"""Duplicate receipt and claim detection for Tarang Pharma Distribution."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.integrity_checks import normalize_plate
from app.normalization import (
    MAX_PLAUSIBLE_YEAR,
    MIN_PLAUSIBLE_YEAR,
    normalize_amount,
    normalize_date,
    normalize_receipt_number,
    normalize_text,
)


# Strongest evidence first; a claim reports its strongest match type.
MATCH_STRENGTH = {"exact_image": 4, "same_bill": 3, "parking_overlap": 2, "possible": 1}

# A ticket timestamp "dd/mm/yy hh:mm"; OCR can glue the time to the year
# ("13/06/2614:56"), which the two-digit year alternative still reads.
PARKING_TIMESTAMP = re.compile(
    r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\s*:?\s*(\d{1,2}):(\d{2})(?!\d)"
)
PARKING_LABEL = re.compile(r"(?im)^\W*(in|out)\b")


def _normalized_vendor(value: object) -> str:
    """Normalize vendor text, ignoring case, spacing and punctuation."""
    return re.sub(r"[^a-z0-9]", "", normalize_text(value).casefold())


def parking_interval(raw_text: Any, receipt_date: Any = "") -> tuple[str, int, int] | None:
    """Return (ISO date, entry minute, exit minute) printed on a parking ticket.

    Only a ticket showing In and Out labels and exactly two timestamps on one
    valid date, with the exit after the entry, gives an interval. When the
    receipt date was read, it must agree. Anything else is uncertain: None.
    """
    text = "" if raw_text is None else str(raw_text)
    if {label.casefold() for label in PARKING_LABEL.findall(text)} != {"in", "out"}:
        return None
    stamps = PARKING_TIMESTAMP.findall(text)
    if len(stamps) != 2:
        return None

    moments = []
    for day, month, year, hour, minute in stamps:
        full_year = int(year) + (2000 if len(year) == 2 else 0)
        if not MIN_PLAUSIBLE_YEAR <= full_year <= MAX_PLAUSIBLE_YEAR:
            return None
        try:
            moments.append(datetime(full_year, int(month), int(day), int(hour), int(minute)))
        except ValueError:
            return None

    entry, exit_ = moments
    if entry.date() != exit_.date() or exit_ <= entry:
        return None
    date = entry.strftime("%Y-%m-%d")
    read_date = normalize_date(receipt_date)
    if read_date and read_date != date:
        return None
    return date, entry.hour * 60 + entry.minute, exit_.hour * 60 + exit_.minute


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def detect_duplicates(
    claims: list[dict[str, Any]],
    receipts: dict[str, dict[str, Any]] | None = None,
    vehicle_registry: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Flag possible duplicate claims using receipt evidence.

    Returns a result keyed by claim_id. Match types, strongest first:
      exact_image     - the same image file (by hash) was submitted again;
      same_bill       - same vendor and receipt number, and the amount or the
                        bill date also agrees; for parking, also the same
                        ticket number, plate, date and entry-exit times when
                        OCR read the car-park name differently;
      parking_overlap - parking tickets for the same vehicle at different car
                        parks with overlapping entry-exit times on one date;
                        the tickets conflict, but which one is wrong is not
                        established. Not a duplicate bill;
      possible        - same vendor and receipt number with conflicting amount
                        and date, or same vendor, amount and bill date (both
                        dates read) without a receipt number match.
    Fixed-fee parking repeats daily by policy, so parking claims are only
    matched by ticket number, image or an overlapping stay, never by vendor
    and amount alone. Parking times come from the OCR text ("raw_text") and
    the plate from "vehicle_no"; when vehicle_registry (normalized plate ->
    employee ID) is given, the plate must be registered. A missing or
    unreadable plate, time or date is uncertain and never matched.
    "matched" maps each related claim ID to the type of that pair's match,
    and "evidence" to what matched.
    A match between different employees is labelled, not judged: who paid
    the bill cannot be established from the receipt. Missing receipt
    identifiers are not fabricated, and every match requires manual review.
    """
    receipts = receipts or {}
    prepared: list[dict[str, Any]] = []

    for claim in claims:
        claim_id = normalize_text(claim.get("claim_id"))
        receipt = receipts.get(claim_id, {})
        amount = normalize_amount(
            receipt.get("total_amount", claim.get("amount_claimed"))
        )
        category = normalize_text(claim.get("category")).casefold()

        prepared.append(
            {
                "claim_id": claim_id,
                "emp_id": normalize_text(claim.get("emp_id")),
                "category": category,
                "vendor": _normalized_vendor(
                    receipt.get("vendor") or claim.get("vendor")
                ),
                "date": normalize_date(
                    receipt.get("receipt_date") or claim.get("expense_date")
                ),
                "number": normalize_receipt_number(
                    receipt.get("receipt_number")
                ),
                "amount": amount,
                "image_hash": normalize_text(receipt.get("image_sha256")),
                "ticket_vendor": normalize_text(receipt.get("vendor")),
                "plate": normalize_plate(receipt.get("vehicle_no")),
                "parking": (
                    parking_interval(receipt.get("raw_text"), receipt.get("receipt_date"))
                    if category == "parking"
                    else None
                ),
            }
        )

    by_id = {item["claim_id"]: item for item in prepared if item["claim_id"]}
    # claim_id -> other claim_id -> (match type, what matched)
    matches: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)

    def record(
        first: dict[str, Any], second: dict[str, Any], kind: str, evidence: str
    ) -> None:
        for item, other in ((first, second), (second, first)):
            current = matches[item["claim_id"]].get(other["claim_id"])
            if current is None or MATCH_STRENGTH[kind] > MATCH_STRENGTH[current[0]]:
                matches[item["claim_id"]][other["claim_id"]] = (kind, evidence)

    def pairs(group: list[dict[str, Any]]):
        for index, item in enumerate(group):
            for other in group[index + 1:]:
                if item["claim_id"] != other["claim_id"]:
                    yield item, other

    by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_receipt: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in by_id.values():
        if item["image_hash"]:
            by_image[item["image_hash"]].append(item)
        if item["number"] and item["vendor"]:
            by_receipt[(item["vendor"], item["number"])].append(item)

    for group in by_image.values():
        for item, other in pairs(group):
            record(item, other, "exact_image", "identical receipt image")

    for group in by_receipt.values():
        for item, other in pairs(group):
            same_amount = (
                item["amount"] is not None
                and other["amount"] is not None
                and abs(item["amount"] - other["amount"]) <= 1
            )
            same_date = bool(item["date"]) and item["date"] == other["date"]
            agreeing = [
                label for label, ok in (("amount", same_amount), ("bill date", same_date)) if ok
            ]
            if agreeing:
                record(
                    item, other, "same_bill",
                    "same vendor and receipt number, same " + " and ".join(agreeing),
                )
            else:
                record(
                    item, other, "possible",
                    "same vendor and receipt number, but amount and bill date differ or are unread",
                )

    # Weaker evidence is surfaced for review, not treated as a confirmed duplicate.
    items = [item for item in by_id.values() if item["category"] != "parking"]
    for item, other in pairs(items):
        if not item["vendor"] or item["vendor"] != other["vendor"]:
            continue
        if item["amount"] is None or item["amount"] != other["amount"]:
            continue
        if not item["date"] or item["date"] != other["date"]:
            continue
        record(
            item, other, "possible",
            "same vendor, amount and bill date; receipt number not matched",
        )

    # One vehicle cannot be parked in two car parks at the same time.
    tickets = [
        item for item in by_id.values()
        if item["parking"] and item["plate"] and item["ticket_vendor"]
        and (vehicle_registry is None or item["plate"] in vehicle_registry)
    ]
    for item, other in pairs(tickets):
        (date, start, end), (other_date, other_start, other_end) = item["parking"], other["parking"]
        if item["plate"] != other["plate"] or date != other_date:
            continue
        if item["image_hash"] and item["image_hash"] == other["image_hash"]:
            continue  # already an exact_image duplicate
        if (
            item["number"] and item["number"] == other["number"]
            and (start, end) == (other_start, other_end)
        ):
            # One physical ticket whose car-park name OCR read differently on
            # each copy: a duplicate, not two tickets that conflict. A shared
            # number with different times is not enough to merge two tickets.
            record(
                item, other, "same_bill",
                "same parking ticket number, vehicle, date and entry-exit times; "
                "car-park name read differently",
            )
            continue
        if _normalized_vendor(item["ticket_vendor"]) == _normalized_vendor(other["ticket_vendor"]):
            continue
        if start < other_end and other_start < end:
            record(
                item, other, "parking_overlap",
                f"same vehicle {item['plate']} on {date} at {item['ticket_vendor']} "
                f"{_clock(start)}-{_clock(end)} ({item['claim_id']}) and at "
                f"{other['ticket_vendor']} {_clock(other_start)}-{_clock(other_end)} "
                f"({other['claim_id']}); the parking times overlap, so the tickets "
                "conflict. Which ticket is wrong is not established",
            )

    results: dict[str, dict[str, Any]] = {}
    for claim_id, item in by_id.items():
        found = matches.get(claim_id, {})
        result: dict[str, Any] = {
            "duplicate_detected": False,
            "possible_matches": [],
            "reason": "",
            "match_type": "",
            "cross_employee": False,
            "matched": {},
            "evidence": {},
        }
        if found:
            strongest = max(
                (kind for kind, _ in found.values()), key=MATCH_STRENGTH.__getitem__
            )
            labels = {
                "exact_image": "Duplicate of", "same_bill": "Duplicate of",
                "parking_overlap": "Parking time conflict with", "possible": "Possible duplicate of",
            }
            parts = []
            cross = []
            for other_id, (kind, evidence) in found.items():
                other = by_id[other_id]
                different = (
                    other["emp_id"] and item["emp_id"] and other["emp_id"] != item["emp_id"]
                )
                if different:
                    cross.append(other_id)
                parts.append(
                    f"{labels[kind]} {other_id}: {evidence}"
                    + ("; different employee, payer not established" if different else "")
                )
            result.update(
                duplicate_detected=strongest in {"exact_image", "same_bill"},
                possible_matches=list(found),
                reason="; ".join(parts) + ". Verify before payment.",
                match_type=strongest,
                cross_employee=bool(cross),
                matched={other_id: kind for other_id, (kind, _) in found.items()},
                evidence={other_id: evidence for other_id, (_, evidence) in found.items()},
            )
        results[claim_id] = result

    return results
