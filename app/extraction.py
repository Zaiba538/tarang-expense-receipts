
"""OCR-based receipt extraction for Tarang Pharma Distribution."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.normalization import normalize_amount, normalize_date, normalize_text


@lru_cache(maxsize=1)
def _get_ocr() -> Any:
    """Initialize PaddleOCR once per process."""
    from paddleocr import PaddleOCR

    return PaddleOCR(use_textline_orientation=True, lang="en")


def _collect_text(value: Any) -> list[str]:
    """Collect recognized text from common PaddleOCR result structures."""
    lines: list[str] = []

    if value is None:
        return lines

    if isinstance(value, dict):
        texts = value.get("rec_texts", [])
        if isinstance(texts, (list, tuple)):
            lines.extend(str(item) for item in texts if item is not None)

        # Support alternative result formats.
        for key in ("text", "texts", "res"):
            if key in value and value[key] is not texts:
                lines.extend(_collect_text(value[key]))

        return lines

    if isinstance(value, (list, tuple)):
        # PaddleOCR's older format: [box, (text, confidence)].
        if (
            len(value) >= 2
            and isinstance(value[1], (list, tuple))
            and value[1]
            and isinstance(value[1][0], str)
        ):
            lines.append(value[1][0])
            return lines

        for item in value:
            lines.extend(_collect_text(item))

        return lines

    # Some PaddleOCR result objects expose a dictionary conversion method.
    if hasattr(value, "json"):
        try:
            converted = value.json
            if callable(converted):
                converted = converted()
            if isinstance(converted, dict):
                return _collect_text(converted)
        except Exception:
            pass

    if hasattr(value, "res"):
        try:
            return _collect_text(value.res)
        except Exception:
            pass

    return lines


def _extract_amount(text: str, lines: list[str]) -> Any:
    """Extract an amount associated with a recognizable currency or total label."""
    amount_pattern = r"([\d,]+(?:\.\d{1,2})?)"
    currency_pattern = r"(?:INR|Rs\.?|₹)\s*"

    # Prefer amounts explicitly associated with total labels.
    total_patterns = [
        rf"(?im)^\s*(?:grand\s+total|total\s+amount|amount\s+payable|net\s+amount|total)\s*[:\-]?\s*{currency_pattern}?{amount_pattern}\b",
        rf"(?im)^\s*(?:grand\s+total|total\s+amount|amount\s+payable|net\s+amount|total)\s*$\s*\n\s*{currency_pattern}?{amount_pattern}\b",
    ]

    for pattern in total_patterns:
        matches = re.findall(pattern, text)
        if matches:
            value = matches[-1]
            if isinstance(value, tuple):
                value = value[-1]
            return normalize_amount(value)

    # Look near explicit amount labels.
    for index, line in enumerate(lines):
        if re.search(r"(?i)\bamount\b", line):
            candidates = [line]
            if index > 0:
                candidates.append(lines[index - 1])
            if index + 1 < len(lines):
                candidates.append(lines[index + 1])

            for candidate in candidates:
                match = re.search(
                    rf"(?i)(?:INR|Rs\.?|₹)\s*{amount_pattern}|{amount_pattern}\s*/-",
                    candidate,
                )
                if match:
                    value = next((group for group in match.groups() if group), None)
                    if value:
                        return normalize_amount(value)

    # Last resort: accept a currency-marked amount, never arbitrary digits.
    for line in lines:
        match = re.search(
            rf"(?i)(?:INR|Rs\.?|₹)\s*{amount_pattern}\b",
            line,
        )
        if match:
            return normalize_amount(match.group(1))

    return None


def extract_receipt_fields(image_path: str | Path) -> dict[str, Any]:
    """Extract receipt fields and preserve uncertainty for manual review."""
    path = Path(image_path)

    result: dict[str, Any] = {
        "vendor": "",
        "receipt_date": "",
        "receipt_number": "",
        "gstin": "",
        "total_amount": None,
        "vehicle_no": "",
        "raw_text": "",
        "readable": False,
        "errors": [],
    }

    if not path.is_file():
        result["errors"].append("image_file_not_found")
        return result

    try:
        ocr_result = _get_ocr().predict(str(path))
        lines = [
            normalize_text(item)
            for item in _collect_text(ocr_result)
            if normalize_text(item)
        ]

        raw_text = "\n".join(lines)
        result["raw_text"] = raw_text
        result["readable"] = bool(raw_text.strip())

        if not raw_text:
            result["errors"].append("no_text_detected")
            return result

        gstin_match = re.search(
            r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
            raw_text.upper(),
        )
        if gstin_match:
            result["gstin"] = gstin_match.group(0)

        date_patterns = [
            r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
            r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
        ]
        for pattern in date_patterns:
            for candidate in re.findall(pattern, raw_text):
                parsed = normalize_date(candidate)
                if parsed:
                    result["receipt_date"] = parsed
                    break
            if result["receipt_date"]:
                break

        number_patterns = [
            r"(?im)\b(?:invoice|receipt|bill)\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{2,})",
            r"(?im)\b(?:invoice|receipt)\s*[:#]\s*([A-Z0-9][A-Z0-9/\-]{2,})",
            r"(?im)\bAWB\s*(?:no\.?|number|#)?\s*[:#]?\s*([A-Z0-9][A-Z0-9/\-]{2,})",
            r"(?im)\bticket\s*no\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9/\-]{2,})",
        ]
        for pattern in number_patterns:
            match = re.search(pattern, raw_text)
            if match:
                result["receipt_number"] = match.group(1).strip()
                break

        vehicle_match = re.search(
            r"(?im)\b(?:vehicle|veh)\s*(?:no\.?|number|#)\s*[:\-]?\s*"
            r"([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\b",
            raw_text,
        )
        if vehicle_match:
            result["vehicle_no"] = re.sub(
                r"\s+", "", vehicle_match.group(1).upper()
            )

        result["total_amount"] = _extract_amount(raw_text, lines)

        excluded_vendor_terms = (
            "gstin", "invoice", "receipt", "date", "time",
            "tax invoice", "bill no", "receipt no", "booking receipt",
        )
        for line in lines:
            if (
                len(line) >= 3
                and not re.fullmatch(r"[\d\s./:-]+", line)
                and not any(
                    term in line.casefold() for term in excluded_vendor_terms
                )
            ):
                result["vendor"] = line
                break

        return result

    except Exception as exc:
        result["errors"].append(
            f"ocr_processing_failed: {type(exc).__name__}: {exc}"
        )
        return result
