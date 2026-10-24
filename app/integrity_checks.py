
"""Receipt integrity checks for Tarang Pharma Distribution.

Each check uses only evidence printed on the receipt. When the receipt does
not carry enough evidence to reach a conclusion, the check returns no finding
instead of guessing. A finding never states a "corrected" amount: it only says
that the printed figures do not support each other, which may be an altered
bill or an OCR misread, and the claim goes to review.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.normalization import normalize_amount, normalize_text


ARITHMETIC_TOLERANCE = Decimal("1.00")
FUEL_TOLERANCE = Decimal("2.00")

# Printed text addressed to approvers or automated processing. Receipts are
# untrusted input: such text is reported, never obeyed. Every pattern needs
# an instruction-like construction, because ordinary receipts print words
# such as "Authorised Signatory" and "Check-in".
_CHECK_WORDS = (
    r"(?:checks?|verification|validation|rules?|polic(?:y|ies)|review|"
    r"duplicates?|audit|instructions?)"
)
_ADDRESSEES = (
    r"(?:ai|assistant|model|llm|bot|chatbot|system|reviewer|auditor|"
    r"approver|clerk|finance)"
)
HOSTILE_PATTERNS = [
    re.compile(r"(?i)\bpre[\s-]*(?:verified|approved|audited|cleared)"),
    re.compile(r"(?i)\bautomated\s+(?:processing|system|review|approval)"),
    re.compile(r"(?i)\b(?:please\s+)?approve\s+(?:it|this|the\s+(?:claim|bill|expense))\b"),
    re.compile(r"(?i)\bplease\s+approve\b"),
    re.compile(r"(?i)\bauto[\s-]*approv"),
    re.compile(r"(?i)\b(?:skip|bypass|ignore|override|disable|disregard)\b.{0,40}\b" + _CHECK_WORDS + r"\b"),
    re.compile(r"(?i)\bdo\s*n[o']?t\s+(?:review|check|verify|query|flag|audit|investigate)\b"),
    re.compile(r"(?i)\bno\s+(?:review|verification|checks?|audit)\s+(?:is\s+)?(?:needed|required)\b"),
    re.compile(r"(?i)\bsystem\s*[:=]"),
    re.compile(r"(?i)\b(?:decision|status|verdict|action)\s*[:=]\s*(?:approve|approved|accept|accepted|pass|ok)\b"),
    re.compile(r"(?i)\bapproved\s+by\b"),
    re.compile(r"(?i)\balready\s+(?:verified|approved|reconciled|checked)\b"),
    re.compile(r"(?i)\breconciled\s+by\b"),
    re.compile(r"(?i)\bin\s+your\s+(?:output|response|answer|reply)\b"),
    re.compile(r"(?i)\b(?:note|message|attention|instructions?)\s+(?:to|for)\s+(?:the\s+)?" + _ADDRESSEES + r"\b"),
    re.compile(
        r"(?i)\b(?:ai|assistant|language\s+model|llm|chatbot|reviewer|auditor|approver)s?"
        r"\s*[:,-]?\s*(?:please\s+)?(?:approve|ignore|skip|bypass|mark|treat|accept|do\s+not)\b"
    ),
]

PLATE_PATTERN = re.compile(r"[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}")

_UNITS = {
    word: value
    for value, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )
}
_TENS = {
    word: 10 * (index + 2)
    for index, word in enumerate(
        "twenty thirty forty fifty sixty seventy eighty ninety".split()
    )
}
_FILLER = {"rupees", "rupee", "rs", "only", "and", "in", "words", "amount"}


def find_hostile_text(text: Any) -> list[str]:
    """Return receipt lines that try to instruct approvers or automation."""
    lines = [normalize_text(line) for line in str(text or "").splitlines()]
    return [
        line for line in lines
        if line and any(pattern.search(line) for pattern in HOSTILE_PATTERNS)
    ]


def _figures(text: str) -> list[Decimal]:
    """Return every decimal money figure printed on the receipt."""
    figures = []
    for raw in re.findall(r"(?<![\d.])\d[\d,]*\.\d{2}(?!\d)", text):
        try:
            figures.append(Decimal(raw.replace(",", "")))
        except InvalidOperation:
            continue
    return figures


def _gst_rate(text: str) -> Decimal | None:
    """Return the total printed GST rate; OCR sometimes reads '@' as '0'."""
    rate = r"\s*[@0]?\s*(\d{1,2}(?:\.\d+)?)\s*%"
    # Intra-state bills charge equal CGST and SGST, so CGST alone fixes the
    # total rate even when OCR garbles the SGST label (e.g. "SG5T").
    central = re.search(r"(?i)CGST" + rate, text)
    if central:
        return Decimal(central.group(1)) * 2
    single = re.search(r"(?i)GST" + rate, text)
    return Decimal(single.group(1)) if single else None


def _check_fuel(text: str, total: Decimal) -> str:
    rate = re.search(r"(?i)Rate\s*\(Rs/L\)\s*:?\s*(\d+\.\d+)", text)
    volume = re.search(r"(?i)Volume\s*\(L\)\s*:?\s*(\d+\.\d+)", text)
    if not rate or not volume:
        return ""
    expected = Decimal(rate.group(1)) * Decimal(volume.group(1))
    if abs(expected - total) > FUEL_TOLERANCE:
        return "fuel_total_not_supported_by_rate_and_volume"
    return ""


def _check_tax(text: str, total: Decimal, rate: Decimal) -> str:
    multiplier = 1 + rate / 100
    candidates = [figure for figure in _figures(text) if figure != total]
    if not candidates:
        return ""
    # OCR may list figures out of order, so any printed figure can be the base.
    if any(
        abs(figure * multiplier - total) <= ARITHMETIC_TOLERANCE
        for figure in candidates
    ):
        return ""
    return "total_not_supported_by_tax_arithmetic"


def _check_itemised(text: str, total: Decimal) -> str:
    lines = [line.strip() for line in text.splitlines()]
    start = next(
        (index for index, line in enumerate(lines) if re.search(r"(?i)particulars", line)),
        None,
    )
    if start is None:
        return ""
    values = [int(line) for line in lines[start + 1:] if re.fullmatch(r"\d{1,4}", line)]
    if total != total.to_integral_value() or int(total) not in values:
        return ""
    values.remove(int(total))
    if len(values) < 2:
        return ""
    if sum(values) != int(total):
        return "total_not_supported_by_line_items"
    return ""


def words_to_amount(phrase: str) -> Decimal | None:
    """Parse an amount written in words; return None unless every word is known."""
    words = re.findall(r"[a-z]+", phrase.casefold())
    if not words:
        return None

    total = current = 0
    found = False
    for word in words:
        if word in _UNITS:
            current += _UNITS[word]
            found = True
        elif word in _TENS:
            current += _TENS[word]
            found = True
        elif word == "hundred":
            current *= 100
        elif word == "thousand":
            total += current * 1000
            current = 0
        elif word == "lakh":
            total += current * 100000
            current = 0
        elif word not in _FILLER:
            return None
    return Decimal(total + current) if found else None


def _amount_in_words(text: str) -> Decimal | None:
    for line in str(text).splitlines():
        if re.search(r"(?i)\bonly\b", line):
            line = re.sub(r"(?i)^.*?\bin\s+words\)?\s*:?", "", line)
            amount = words_to_amount(line)
            if amount is not None:
                return amount
    return None


def enhanced_pass_fields(receipt: dict[str, Any]) -> list[str]:
    """Fields the enhanced second OCR pass filled (a list, or '; '-joined in CSV files)."""
    value = receipt.get("filled_by_enhanced_pass") or []
    if isinstance(value, str):
        value = value.split(";")
    return [str(field).strip() for field in value if str(field).strip()]


def total_source_text(receipt: dict[str, Any]) -> str:
    """
    Return the OCR text the printed total was read from. When the enhanced
    second pass filled the total, the bill's figures are checked on that pass:
    checking its total against figures from the first pass, which could not
    read the total, mixes two readings of one bill.
    """
    if "total_amount" in enhanced_pass_fields(receipt):
        return str(receipt.get("raw_text_enhanced") or "")
    return str(receipt.get("raw_text") or "")


def check_receipt_integrity(
    raw_text: Any,
    total_amount: Any,
    amount_claimed: Any = None,
) -> list[dict[str, str]]:
    """
    Compare the printed total with the receipt's own supporting figures.

    Returns findings as {"code", "message"}. An empty list means either the
    figures agree or the receipt did not carry enough evidence to check.
    """
    text = str(raw_text or "")
    if not text.strip():
        return []

    findings: list[dict[str, str]] = []
    total = normalize_amount(total_amount)

    if total is not None:
        if re.search(r"(?i)Rate\s*\(Rs/L\)", text):
            code = _check_fuel(text, total)
        else:
            rate = _gst_rate(text)
            code = (
                _check_tax(text, total, rate)
                if rate is not None
                else _check_itemised(text, total)
            )
        if code:
            findings.append({
                "code": code,
                "message": (
                    f"Printed total Rs {total:,.2f} is not supported by the "
                    "bill's own figures; possible altered total or OCR misread. "
                    "Verify against the original bill."
                ),
            })

    in_words = _amount_in_words(text)
    if in_words is not None:
        compared = total if total is not None else normalize_amount(amount_claimed)
        if compared is not None and abs(in_words - compared) > ARITHMETIC_TOLERANCE:
            findings.append({
                "code": "amount_in_words_contradiction",
                "message": (
                    f"Amount in words (Rs {in_words:,.2f}) contradicts the "
                    f"{'printed total' if total is not None else 'claimed amount'} "
                    f"(Rs {compared:,.2f}); possible altered figure."
                ),
            })

    return findings


def normalize_plate(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_text(value).upper())


def classify_vehicle(
    bill_plate: Any,
    employee_plate: Any,
    vehicle_registry: dict[str, str] | None = None,
    emp_id: str = "",
) -> dict[str, str]:
    """
    Compare the plate on a fuel bill with the claimant's registered vehicle.

    Status is one of: match, missing, uncertain, other_employee, mismatch.
    OCR that does not yield a complete plate, or a plate one character away
    from the claimant's, is uncertain rather than a confirmed mismatch.
    """
    bill = normalize_plate(bill_plate)
    own = normalize_plate(employee_plate)

    if not bill:
        return {"status": "missing", "message": "Vehicle number is not readable on the fuel bill."}
    if own and bill == own:
        return {"status": "match", "message": ""}
    if not PLATE_PATTERN.fullmatch(bill):
        return {
            "status": "uncertain",
            "message": "Vehicle number on the fuel bill could not be read reliably; verify it.",
        }

    owner = (vehicle_registry or {}).get(bill, "")
    if owner and owner != emp_id:
        return {
            "status": "other_employee",
            "message": (
                f"Fuel bill vehicle {bill} is registered to another employee "
                f"({owner}); verify who paid before payment."
            ),
        }
    if own and len(bill) == len(own) and sum(a != b for a, b in zip(bill, own)) == 1:
        return {
            "status": "uncertain",
            "message": (
                f"Fuel bill vehicle {bill} differs from the employee's vehicle by "
                "one character; possibly an OCR misread. Verify it."
            ),
        }
    return {
        "status": "mismatch",
        "message": "Fuel bill vehicle number does not match employee records.",
    }
