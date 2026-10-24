
"""OCR-based receipt extraction for Tarang Pharma Distribution.

Prioritizes explicitly labelled receipt dates, avoids selecting unrelated
dates where possible, and uses conservative vendor and amount extraction.
Uncertain fields remain empty for downstream review.
"""

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

        for key in ("text", "texts", "res"):
            if key in value and value[key] is not texts:
                lines.extend(_collect_text(value[key]))

        return lines

    if isinstance(value, (list, tuple)):
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


DATE_TOKEN = re.compile(
    r"(?<!\d)(?:"
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|"
    r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|"
    r"\d{1,2}[-/][A-Za-z]{3,9}[-/]\d{2,4}"
    r"|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"
    r"|"
    r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}"
    r")(?!\d)",
    re.IGNORECASE,
)


def _extract_date(lines: list[str]) -> str:
    """Prefer transaction dates explicitly labelled on the receipt."""
    date_pattern = DATE_TOKEN

    candidates: list[tuple[int, int, str]] = []
    seen: set[tuple[str, int]] = set()

    for index, line in enumerate(lines):
        matches = list(date_pattern.finditer(line))
        context = line

        if not matches and re.search(
            r"(?i)\b(?:date|dated|bill\s+date|invoice\s+date)\b",
            line,
        ):
            if index + 1 < len(lines):
                context = line + " " + lines[index + 1]
                matches = list(date_pattern.finditer(context))

        for match in matches:
            raw = match.group(0).strip()
            parsed = normalize_date(raw)
            if not parsed:
                continue

            lower = context.casefold()
            if re.search(
                r"\b(?:due date|expiry date|expiration date|"
                r"delivery date|valid until|valid through)\b",
                lower,
            ):
                continue

            score = 0
            if re.search(
                r"(?i)\b(?:date|dated|bill\s+date|invoice\s+date)\b",
                context,
            ):
                score += 100
            if re.search(
                r"(?i)\b(?:time|printed|generated|downloaded)\b", lower
            ):
                score -= 20
            if re.search(r"(?i)\b(?:due|expiry|delivery)\b", lower):
                score -= 80

            score -= min(index, 20)

            identity = (parsed, index)
            if identity not in seen:
                candidates.append((score, index, parsed))
                seen.add(identity)

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (-item[0], item[1]))
    best_score, _, best_date = candidates[0]

    if best_score < 0:
        # No labelled date. An unlabelled date (a parking ticket's entry
        # time, a handwritten bill) is used only when every plausible date
        # on the receipt agrees; conflicting dates stay blank for review.
        distinct = {parsed for _, _, parsed in candidates}
        return best_date if len(distinct) == 1 else ""

    return best_date


def _has_conflicting_dates(lines: list[str]) -> bool:
    """True when the receipt shows more than one distinct plausible date."""
    found = {
        normalize_date(match.group(0))
        for line in lines
        for match in DATE_TOKEN.finditer(line)
    }
    return len(found - {""}) > 1


def _separate_glued_time(line: str) -> str:
    """Split a time OCR glued onto a four-digit year ('24-06-202616:24')."""
    return re.sub(
        r"(?<!\d)(\d{1,2}[-/.]\d{1,2}[-/.](?:19|20)\d{2})(\d{1,2}:\d{2})",
        r"\1 \2",
        line,
    )


def _repair_slash_misread_date(lines: list[str]) -> str:
    """
    Read a labelled date whose separators OCR read as '1' ('25/712026',
    '171712026'). Accepted only when exactly one valid date fits; otherwise
    blank.
    """
    from datetime import date

    from app.normalization import MAX_PLAUSIBLE_YEAR, MIN_PLAUSIBLE_YEAR

    candidates: set[str] = set()
    for index, line in enumerate(lines):
        label = re.search(r"(?i)\bdate\b\s*[:.]?\s*", line)
        if not label:
            continue
        token = line[label.end():].strip() or (
            lines[index + 1].strip() if index + 1 < len(lines) else ""
        )
        match = re.fullmatch(r"(\d[\d/\-.]{3,5})((?:19|20)\d{2})", token)
        if not match:
            continue
        head, year = match.group(1), int(match.group(2))
        if not MIN_PLAUSIBLE_YEAR <= year <= MAX_PLAUSIBLE_YEAR:
            continue
        # head = day, separator, month, separator; a separator is a real
        # one or a '1' that was a misread slash.
        for day_len in (1, 2):
            for month_len in (1, 2):
                if day_len + month_len + 2 != len(head):
                    continue
                day = head[:day_len]
                sep1 = head[day_len]
                month = head[day_len + 1:day_len + 1 + month_len]
                sep2 = head[-1]
                if not (day.isdigit() and month.isdigit()):
                    continue
                if sep1 not in "/-.1" or sep2 not in "/-.1":
                    continue
                if sep1 in "/-." and sep2 in "/-.":
                    continue  # nothing was misread; normal parsing applies
                try:
                    candidates.add(date(year, int(month), int(day)).isoformat())
                except ValueError:
                    continue
    return candidates.pop() if len(candidates) == 1 else ""


def _extract_details(lines: list[str]) -> dict[str, str]:
    """Route, distance and fuel details printed on the same line as a label.

    Values on a separate line are not guessed: OCR often scatters labels
    and handwritten values, so only same-line values are taken.
    """
    text = "\n".join(lines)

    def first(pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1).strip(" :|") if match else ""

    return {
        "route_from": first(r"(?im)\b(?:from|origin)[ \t]*:[ \t]*([A-Za-z][A-Za-z .&-]{1,40}?)[ \t]*(?:\bto\b[ \t]*:|$)"),
        "route_to": first(r"(?im)\b(?:to|dest(?:ination)?)[ \t]*:[ \t]*([A-Za-z][A-Za-z .&-]{1,40}?)[ \t]*$"),
        "km": first(r"(?im)\bkm[ \t]*:[ \t]*(\d{1,4}(?:\.\d+)?)\b"),
        "fuel_rate_per_litre": first(r"(?im)\brate[ \t]*\([ \t]*rs[ \t]*/[ \t]*l[ \t]*\)[ \t]*:?[ \t]*(\d+(?:\.\d+)?)"),
        "fuel_volume_litres": first(r"(?im)\bvolume[ \t]*\([ \t]*l[ \t]*\)[ \t]*:?[ \t]*(\d+(?:\.\d+)?)"),
    }


# A value line after one of these labels is that reading, not an amount.
NON_AMOUNT_LABEL = re.compile(r"(?i)\s*(?:km|kms|qty|pcs|wt|weight)\s*[:.]?\s*")

# Indian plate: state (2 letters), district (1-2 digits), series (1-3
# letters), number (1-4 digits). OCR may put one punctuation mark between
# parts ("MH34'CP 5187").
_PLATE_SEP = r"[ \t]*['’`.\-]?[ \t]*"
_PLATE = (
    r"([A-Z]{2}" + _PLATE_SEP + r"\d{1,2}" + _PLATE_SEP + r"[A-Z0-9]{1,3}"
    + _PLATE_SEP + r"\d{1,4})"
)
_VEHICLE_LABEL = r"\b(?:vehicle|veh|ken)\s*/?\s*(?:no\.?|number|#)"
VEHICLE_LABEL = re.compile(_VEHICLE_LABEL, re.IGNORECASE)
# Series letters OCR commonly reads as digits; only series positions are
# repaired, never the district or number digits.
_SERIES_DIGIT_TO_LETTER = str.maketrans("80152", "BOISZ")


def _plate_from(token: str) -> tuple[str, bool]:
    """Normalise a captured plate; ('', False) unless it is a valid plate.

    Returns (plate, repaired). Digits in the series letters are read as the
    letters they resemble only when the plate's structure leaves a single
    reading.
    """
    compact = re.sub(r"[^A-Z0-9]", "", token.upper())
    as_printed, repaired = set(), set()
    for district_len in (1, 2):
        series = compact[2 + district_len:len(compact) - 4]
        state, district, number = compact[:2], compact[2:2 + district_len], compact[-4:]
        if not (1 <= len(series) <= 3 and state.isalpha() and district.isdigit() and number.isdigit()):
            continue
        if series.isalpha():
            as_printed.add(compact)
        else:
            fixed = series.translate(_SERIES_DIGIT_TO_LETTER)
            if fixed.isalpha():
                repaired.add(state + district + fixed + number)
    # A plate valid as printed is never re-read; a repair is used only when
    # nothing is valid as printed and exactly one repair fits.
    if as_printed:
        return compact, False
    if len(repaired) == 1:
        return repaired.pop(), True
    return "", False


def _extract_vehicle(lines: list[str]) -> tuple[str, list[str]]:
    """
    Vehicle number printed after a vehicle label, or on a plate-only line
    within three lines of one (handwritten cab slips put the plate above the
    label). Returns (plate, notes); blank when no single valid plate fits.
    """
    same_line = re.compile(r"(?im)" + _VEHICLE_LABEL + r"\s*[:\-]?\s*" + _PLATE + r"\b")
    plate_only = re.compile(r"(?i)\s*[:\-]?\s*" + _PLATE + r"(?:\s+km\b.*)?\s*")

    # The label may end one line and the plate start the next ("Veh No" /
    # ": MH31DX0981"), so the labelled form is searched across the text.
    for match in same_line.finditer("\n".join(lines)):
        if "\n" in match.group(0):
            continue  # plate on the next line: checked with its neighbours below
        plate, repaired = _plate_from(match.group(1))
        if plate:
            return plate, (["vehicle_no_series_read_from_digits"] if repaired else [])

    found: dict[str, bool] = {}
    for index, line in enumerate(lines):
        if not VEHICLE_LABEL.search(line):
            continue
        for neighbour in lines[max(0, index - 3):index + 4]:
            match = plate_only.fullmatch(neighbour)
            if match:
                plate, repaired = _plate_from(match.group(1))
                if plate:
                    found[plate] = found.get(plate, False) or repaired
    if len(found) == 1:
        plate, repaired = next(iter(found.items()))
        notes = ["vehicle_no_on_separate_line"]
        if repaired:
            notes.append("vehicle_no_series_read_from_digits")
        return plate, notes
    return "", (["vehicle_no_conflicting_candidates"] if len(found) > 1 else [])


def _extract_receipt_number(text: str) -> str:
    """Extract a bill, invoice, receipt, AWB, or ticket identifier."""
    # OCR misreads "Bill" as "B1ll", "B111" or "Bil"; colons may be full-width.
    patterns = [
        # "Redeipt" and "AMB" are OCR misreads of "Receipt" and "AWB".
        r"(?im)\b(?:invoice|re[cd]e?ipt|B[il1|]{2,3})\s*(?:no\.?|number|#)\s*[:：\-]?\s*([A-Z0-9][A-Z0-9/\-]{2,})",
        r"(?im)\b(?:invoice|re[cd]e?ipt)\s*[:#：]\s*([A-Z0-9][A-Z0-9/\-]{2,})",
        r"(?im)\bA[WM]B\s*(?:no\.?|number|#)?\s*[:#：]?\s*([A-Z0-9][A-Z0-9/\-]{2,})",
        r"(?im)\bticket\s*no\.?\s*[:#：]?\s*([A-Z0-9][A-Z0-9/\-]{2,})",
        # Cab receipts print a bare "No. 8219" at the start of a line.
        r"(?im)^\s*No\s*[.:!：]?\s*(\d[0-9/\-]{2,})",
    ]

    def plausible(value: str) -> bool:
        """Reject captured words such as 'Date' and captured dates."""
        return bool(re.search(r"\d", value)) and not normalize_date(value)

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1).strip()
            if plausible(value):
                return value

    # A label alone on its line, with the number a line or two below.
    lines = [line.strip() for line in text.splitlines()]
    label_only = re.compile(
        r"(?i)^(?:(?:invoice|receipt|B[il1|]{2,3})\s*)?No\s*[.:!：]?$"
    )
    for index, line in enumerate(lines):
        if not label_only.match(line):
            continue
        for candidate in lines[index + 1:index + 3]:
            if re.fullmatch(r"[A-Z]?/?\d{3,}", candidate) and plausible(candidate):
                return candidate

    return ""


FUEL_BRAND_ONLY = re.compile(
    r"(?i)(?:bpcl|hpcl|iocl|indian\s*oil|bharat\s+petroleum|"
    r"hindustan\s+petroleum|nayara(?:\s+energy)?|shell|jio[\s-]*bp)"
)


def _extract_vendor(lines: list[str]) -> str:
    """Choose a plausible merchant name from the receipt header."""
    excluded = re.compile(
        r"(?i)\b(?:gstin|gst|invoice|receipt|tax invoice|bill no|"
        r"receipt no|date|time|phone|mobile|tel|ph|address|"
        r"customer care|www\.|https?://|email|cashier|steward|"
        r"table|thank you|visit again|welcome|original copy|"
        r"duplicate copy|order no|token no)\b"
    )
    address_like = re.compile(
        r"(?i)\b(?:road|rd\.|street|st\.|lane|nagar|chowk|"
        r"wardha|nagpur|maharashtra|pin\s*code)\b"
    )

    candidates: list[tuple[int, int, str]] = []

    for index, line in enumerate(lines[:8]):
        text = normalize_text(line).strip(" -|:")
        if len(text) < 3 or len(text) > 70:
            continue
        if re.fullmatch(r"[\d\s.,:/#\-]+", text):
            continue
        if excluded.search(text):
            continue
        # A fuel slip prints the oil company's logo above the station name;
        # the station is the vendor.
        if FUEL_BRAND_ONLY.fullmatch(text):
            continue

        score = max(0, 12 - index * 2)

        if re.search(r"[A-Za-z]", text):
            score += 2
        if text.isupper():
            score += 3
        if re.search(r"\d", text):
            score -= 3
        if address_like.search(text):
            score -= 5
        if len(text.split()) > 8:
            score -= 3

        candidates.append((score, index, text))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (-item[0], item[1]))
    best_score, _, vendor = candidates[0]

    return vendor if best_score >= 3 else ""


def _extract_amount_in_words(lines: list[str]) -> tuple[str, Any]:
    """Return the amount written in words on the bill, and its value.

    Only a line ending the phrase with "only" is read, and every word must be
    a number word; otherwise ("", None).
    """
    from app.integrity_checks import words_to_amount

    for line in lines:
        if not re.search(r"(?i)\bonly\b", line):
            continue
        phrase = re.sub(r"(?i)^.*?\bin\s+words\)?\s*:?", "", line).strip()
        phrase = re.sub(r"(?i)^\s*rupees\s*:?\s*", "", phrase).strip()
        value = words_to_amount(phrase)
        if value is not None:
            return phrase, value
    return "", None


def _extract_amount(text: str, lines: list[str], words_value: Any = None) -> Any:
    """Extract a likely receipt amount only near a relevant amount label.

    words_value is the bill's own amount in words, when legible. It is used
    only to resolve a figure whose '/-' OCR read as '7-' or '1-'; it is never
    used as the amount by itself.
    """
    total_label = re.compile(
        r"\b(?:grand\s+total|total\s+amount|amount\s+payable|"
        r"net\s+amount|total\s+payable|bill\s+total|total)\b",
        re.IGNORECASE,
    )
    amount_label = re.compile(
        r"\b(?:amount\s*\(\s*(?:rs\.?|inr)\s*\)|"
        r"amount\s+payable|net\s+amount|bill\s+amount|amount)\b",
        re.IGNORECASE,
    )

    # OCR often reads the slash of '1230/-' as 7 or 1 ('12307-').
    slash_misread = re.compile(r"\d+[71]-")

    cleaned = [str(line).strip() for line in lines]
    if not cleaned and text:
        cleaned = [line.strip() for line in text.splitlines()]

    def parse_number(value: str) -> Any:
        return normalize_amount(value.replace(",", "").strip())

    def number_on_line(line: str) -> Any:
        """Accept a standalone amount, including common OCR punctuation errors."""
        candidate = line.strip()
        if not candidate:
            return None

        candidate = re.sub(r"\s+", " ", candidate)

        # The true amount of a slash misread is ambiguous ('12307-' may be
        # 1230 or 12307). Accept a reading only when the bill's own amount
        # in words agrees with it; otherwise leave it blank.
        if slash_misread.fullmatch(candidate):
            if words_value is None:
                return None
            for reading in (candidate[:-2], candidate[:-1]):
                if parse_number(reading) == words_value:
                    return parse_number(reading)
            return None

        # OCR may read a printed trailing '/-' as '-' or add a stray T/I.
        candidate = re.sub(r"\s*(?:/-|[-~])\s*$", "", candidate)
        candidate = re.sub(r"(?<=\d)[TtIl|](?=\s*$)", "", candidate)

        # Handle fragments such as "Rs.", "Amount / Rs", and "Amount Rs.".
        candidate = re.sub(
            r"(?i)^\s*amount\b", "", candidate
        ).strip()
        candidate = re.sub(
            r"(?i)^\s*(?:[/|:]\s*)+", "", candidate
        ).strip()
        candidate = re.sub(
            r"(?i)^\s*(?:₹|Rs\.?|INR)\s*", "", candidate
        ).strip()
        candidate = re.sub(
            r"(?i)\s*(?:₹|Rs\.?|INR)\s*$", "", candidate
        ).strip()
        candidate = re.sub(r"^[\s:|=/()-]+", "", candidate)
        candidate = re.sub(r"[\s:|=/()-]+$", "", candidate)

        match = re.fullmatch(
            r"([0-9][0-9,]*(?:\.\d{1,2})?)", candidate, re.IGNORECASE
        )
        if match:
            return parse_number(match.group(1))

        return None

    def nearby_number(index: int, direction: int, max_steps: int = 2) -> Any:
        for step in range(1, max_steps + 1):
            j = index + direction * step
            if not 0 <= j < len(cleaned):
                break

            candidate = cleaned[j]
            value = number_on_line(candidate)
            # A bare figure right after a Km/Qty/Pcs/Wt label is that reading,
            # not the bill amount ("Km: | 76 | Amount Rs."). A figure marked as
            # rupees ("700/-") is still an amount: OCR scatters the labels.
            if (
                value is not None and j > 0
                and NON_AMOUNT_LABEL.fullmatch(cleaned[j - 1])
                and not re.search(r"(?i)/-|₹|\brs\b", candidate)
            ):
                continue
            if value is not None:
                return value

            # Do not skip past the amount to an unrelated number (e.g. Km).
            if slash_misread.fullmatch(candidate):
                break

            # Label fragments split over lines ("GRAND" / "TOTAL" / "Rs")
            # are skipped; any other text ends the search.
            if candidate and re.search(r"[A-Za-z]{3,}", candidate):
                if not re.fullmatch(
                    r"(?i)(?:₹|rs\.?|inr|amount|amount\s*/?\s*rs\.?|grand|total|grand\s+total)",
                    candidate,
                ):
                    break

        return None

    # 1. Prefer an explicitly labelled total.
    for i, line in enumerate(cleaned):
        label_match = total_label.search(line)
        if not label_match:
            continue

        # A pre-tax subtotal is not the bill total.
        if re.search(r"(?i)\bsub[\s-]*total\b", line):
            continue

        trailing = line[label_match.end():].strip()
        trailing = re.sub(r"^[\s:|=/()-]+", "", trailing)
        value = number_on_line(trailing)
        if value is not None:
            return value

        value = nearby_number(i, 1, max_steps=2)
        if value is not None:
            return value

        value = nearby_number(i, -1, max_steps=2)
        if value is not None:
            return value

    # 2. Handle explicit Amount labels before or after the number.
    for i, line in enumerate(cleaned):
        label_match = amount_label.search(line)
        if not label_match:
            continue

        # "Particulars | Amount" is an item-table column header; the next
        # figure is the first item, not the bill total.
        if re.fullmatch(r"(?i)amount", line.strip()) and any(
            re.search(r"(?i)\bparticulars\b", neighbour)
            for neighbour in cleaned[max(0, i - 1):i + 2]
        ):
            continue

        # Example: "Amount Rs.390" or "Amount (Rs): 300.00".
        suffix = line[label_match.end():].strip()
        suffix = re.sub(r"^[\s:|=/()-]+", "", suffix)
        # A lone digit after the label ("Amount Rs. 1" with "940/-" above)
        # is a handwritten figure OCR split in two; neither part is the
        # total, so leave it blank rather than guess.
        if re.fullmatch(r"(?i)(?:rs\.?\s*)?\d", suffix):
            return None
        value = number_on_line(suffix)
        if value is not None:
            return value

        # Example: "12307-" followed by "Amount Rs.".
        value = nearby_number(i, -1, max_steps=2)
        if value is not None:
            return value

        # Example: "Amount / Rs" followed by "20.00".
        value = nearby_number(i, 1, max_steps=2)
        if value is not None:
            return value

        # 3. Handle parking receipts with a standalone amount between
    # a ticket identifier and descriptive text.
    for i, line in enumerate(cleaned):
        value = number_on_line(line)
        if value is None:
            continue

        # Ignore likely ticket or receipt identifiers.
        if re.search(r"(?i)\b(?:ticket|receipt|bill|invoice)\b", line):
            continue

        # Accept a standalone amount when nearby context indicates parking.
        nearby = " ".join(cleaned[max(0, i - 2):i] + cleaned[i + 1:i + 2])
        if re.search(r"(?i)\b(?:parking|day rate|vehicle parked)\b", nearby):
            return value

    return None    

    


_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_PATTERN = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
_TO_DIGIT = str.maketrans("OIDSBZ", "010582")
_TO_LETTER = str.maketrans("01582", "OISBZ")


def gstin_checksum_valid(gstin: str) -> bool:
    """Check a GSTIN's format, state code and final (mod-36) check character.

    State codes run 01-38, plus 97 (other territory) and 99 (centre
    jurisdiction).
    """
    if not GSTIN_PATTERN.fullmatch(gstin):
        return False
    state = int(gstin[:2])
    if not (1 <= state <= 38 or state in (97, 99)):
        return False
    total = 0
    for position, char in enumerate(gstin[:14]):
        value = _GSTIN_CHARS.index(char) * (2 if position % 2 else 1)
        total += value // 36 + value % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36] == gstin[14]


def _extract_gstin(text: str) -> tuple[str, bool]:
    """
    Return (GSTIN, checksum_failed).

    OCR confuses letters and digits (O/0, I/1), so each 15-character token is
    corrected position by position: state code and PAN digits are digits,
    PAN letters are letters, the 14th character is 'Z'. A corrected value is
    accepted only when its check character validates; a GSTIN-shaped token
    that cannot be validated is reported, not guessed.
    """
    checksum_failed = False
    for token in re.findall(r"(?<![0-9A-Z])[0-9A-Z]{15}(?![0-9A-Z])", text.upper()):
        repaired = (
            token[:2].translate(_TO_DIGIT)
            + token[2:7].translate(_TO_LETTER)
            + token[7:11].translate(_TO_DIGIT)
            + token[11].translate(_TO_LETTER)
            + token[12]
            + ("Z" if token[13] == "2" else token[13])
            + token[14]
        )
        if gstin_checksum_valid(repaired):
            return repaired, False
        if GSTIN_PATTERN.fullmatch(token):
            checksum_failed = True
    return "", checksum_failed


def extract_fields_from_lines(lines: list[str]) -> dict[str, Any]:
    """
    Extract receipt fields from OCR text lines.

    Shared by live extraction and by re-extraction from stored OCR text, so
    both apply exactly the same rules. Uncertain fields stay blank and are
    named in "errors".
    """
    raw_text = "\n".join(lines)
    result: dict[str, Any] = {
        "vendor": "", "receipt_date": "", "receipt_number": "", "gstin": "",
        "total_amount": None, "vehicle_no": "", "amount_in_words": "",
        "amount_in_words_value": None, "route_from": "", "route_to": "",
        "km": "", "fuel_rate_per_litre": "", "fuel_volume_litres": "",
        "notes": [], "errors": [],
    }
    if not raw_text.strip():
        result["errors"].append("no_text_detected")
        return result

    result["gstin"], checksum_failed = _extract_gstin(raw_text)
    if checksum_failed and not result["gstin"]:
        result["errors"].append("gstin_checksum_failed")

    date_lines = [_separate_glued_time(line) for line in lines]
    result["receipt_date"] = _extract_date(date_lines)
    if not result["receipt_date"]:
        result["receipt_date"] = _repair_slash_misread_date(date_lines)
        if result["receipt_date"]:
            result["notes"].append("receipt_date_read_with_misread_separators")
    if not result["receipt_date"]:
        result["errors"].append(
            "receipt_date_conflicting_candidates"
            if _has_conflicting_dates(date_lines)
            else "receipt_date_uncertain_or_missing"
        )

    result["receipt_number"] = _extract_receipt_number(raw_text)

    result["vehicle_no"], vehicle_notes = _extract_vehicle(lines)
    result["notes"].extend(vehicle_notes)

    result["amount_in_words"], result["amount_in_words_value"] = _extract_amount_in_words(lines)
    result["total_amount"] = _extract_amount(raw_text, lines, result["amount_in_words_value"])
    if (
        result["total_amount"] is not None
        and result["amount_in_words_value"] is not None
        and result["total_amount"] != result["amount_in_words_value"]
    ):
        # Kept as printed; the contradiction is flagged, not corrected.
        result["notes"].append("amount_in_words_differs_from_figure")
    result.update(_extract_details(lines))
    result["vendor"] = _extract_vendor(lines)
    if not result["vendor"]:
        result["errors"].append("vendor_uncertain_or_missing")

    return result


# Fields a second, enhanced OCR pass may fill when the first pass left them blank.
FILLABLE_FIELDS = (
    "vendor", "receipt_date", "receipt_number", "gstin", "total_amount",
    "vehicle_no", "amount_in_words", "amount_in_words_value", "route_from",
    "route_to", "km", "fuel_rate_per_litre", "fuel_volume_litres",
)
_FIELD_ERRORS = {
    "vendor": ("vendor_uncertain_or_missing",),
    "receipt_date": ("receipt_date_uncertain_or_missing", "receipt_date_conflicting_candidates"),
}


def needs_enhanced_pass(fields: dict[str, Any]) -> bool:
    """A second pass is tried only when a key field is blank."""
    return any(
        fields.get(key) in (None, "")
        for key in ("receipt_date", "receipt_number", "total_amount")
    )


def combine_passes(primary_lines: list[str], enhanced_lines: list[str] | None) -> dict[str, Any]:
    """
    Extract fields from the first OCR pass, then fill only its blank fields
    from an enhanced second pass. A value read on the first pass is never
    replaced. Used by live extraction and by re-extraction from stored text.
    """
    fields = extract_fields_from_lines(primary_lines)
    fields["filled_by_enhanced_pass"] = []
    if not enhanced_lines:
        return fields

    second = extract_fields_from_lines(enhanced_lines)
    for key in FILLABLE_FIELDS:
        if fields.get(key) in (None, "") and second.get(key) not in (None, ""):
            fields[key] = second[key]
            fields["filled_by_enhanced_pass"].append(key)
            for error in _FIELD_ERRORS.get(key, ()):
                if error in fields["errors"]:
                    fields["errors"].remove(error)
    if "no_text_detected" in fields["errors"] and "\n".join(enhanced_lines).strip():
        fields["errors"].remove("no_text_detected")
    fields["notes"] = [
        note for note in fields["notes"] if note != "amount_in_words_differs_from_figure"
    ]
    if (
        fields["total_amount"] is not None
        and fields["amount_in_words_value"] is not None
        and fields["total_amount"] != fields["amount_in_words_value"]
    ):
        fields["notes"].append("amount_in_words_differs_from_figure")
    return fields


def _enhanced_image(path: Path) -> Path:
    """A 1.5x upscaled, sharpened copy in the system temp folder."""
    import tempfile

    from PIL import Image, ImageFilter

    with Image.open(path) as image:
        image = image.convert("RGB")
        enhanced = image.resize(
            (int(image.width * 1.5), int(image.height * 1.5)), Image.LANCZOS
        ).filter(ImageFilter.SHARPEN)
    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    handle.close()
    enhanced.save(handle.name, quality=95)
    return Path(handle.name)


def _ocr_lines(path: Path) -> list[str]:
    ocr_result = _get_ocr().predict(str(path))
    return [
        normalize_text(item)
        for item in _collect_text(ocr_result)
        if normalize_text(item)
    ]


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
        "raw_text_enhanced": "",
        "readable": False,
        "errors": [],
    }

    if not path.is_file():
        result["errors"].append("image_file_not_found")
        return result

    try:
        lines = _ocr_lines(path)
        enhanced_lines: list[str] = []
        if needs_enhanced_pass(extract_fields_from_lines(lines)):
            enhanced_path = _enhanced_image(path)
            try:
                enhanced_lines = _ocr_lines(enhanced_path)
            finally:
                enhanced_path.unlink(missing_ok=True)

        result["raw_text"] = "\n".join(lines)
        result["raw_text_enhanced"] = "\n".join(enhanced_lines)
        result["readable"] = bool(result["raw_text"].strip() or result["raw_text_enhanced"].strip())

        fields = combine_passes(lines, enhanced_lines)
        result.update({key: value for key, value in fields.items() if key != "errors"})
        result["errors"].extend(fields["errors"])
        return result

    except Exception as exc:
        result["errors"].append(
            f"ocr_processing_failed: {type(exc).__name__}: {exc}"
        )
        return result
