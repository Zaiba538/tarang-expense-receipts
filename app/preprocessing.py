"""Reusable preprocessing helpers for claim and receipt data."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


def clean_text(value: Any) -> str:
    """Return a trimmed string; represent missing values as an empty string."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    return "" if text.casefold() in {"nan", "none", "nat"} else text


def normalize_column_name(value: Any) -> str:
    """Normalize a column name to lowercase snake_case."""
    text = clean_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalize_dataframe_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalized column names."""
    result = frame.copy()
    result.columns = [normalize_column_name(col) for col in result.columns]
    return result


def clean_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with pandas missing values replaced by empty strings."""
    return frame.fillna("").copy()


def parse_amount(value: Any) -> float | None:
    """Parse a currency-like value; return None if no valid number is available."""
    text = clean_text(value)
    if not text:
        return None

    text = text.replace(",", "")
    text = re.sub(r"(?i)\b(?:inr|rs\.?|rupees?)\b", "", text)
    text = text.replace("₹", "").strip()
    match = re.search(r"-?\d+(?:\.\d{1,2})?", text)

    if not match:
        return None

    try:
        amount = float(match.group())
    except ValueError:
        return None

    return amount if pd.notna(amount) else None


def parse_date(value: Any) -> str:
    """Normalize a recognizable date to YYYY-MM-DD; otherwise return blank."""
    text = clean_text(value)
    if not text:
        return ""

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return ""

    return parsed.strftime("%Y-%m-%d")
