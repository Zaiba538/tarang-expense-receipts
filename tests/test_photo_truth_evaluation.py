import pandas as pd

from scripts.evaluate_photo_truth import FIELDS, NONE, UNKNOWN, breakdown, outcome, score


def test_blank_value_is_a_miss_not_correct():
    assert outcome("receipt_date", "2026-07-01", "") == "blank"
    assert outcome("receipt_date", "2026-07-01", "   ") == "blank"
    assert outcome("total_amount", "315.00", "") == "blank"


def test_wrong_non_blank_value_is_separate_from_blank():
    assert outcome("receipt_date", "2026-07-30", "2026-07-03") == "wrong"
    assert outcome("receipt_date", "2026-07-30", "2026-07-30") == "correct"


def test_blank_gstin_is_correct_only_when_no_gstin_is_printed():
    assert outcome("gstin", NONE, "") == "correct"
    assert outcome("gstin", NONE, "27AAAAA0000A1Z5") == "wrong"
    assert outcome("gstin", "27HJXCW9975D1ZJ", "") == "blank"


def _sample():
    row = {field: UNKNOWN for field in FIELDS}
    rows = [
        {**row, "receipt_date": "2026-07-01", "new_receipt_date": ""},
        {**row, "receipt_date": "2026-07-30", "new_receipt_date": "2026-07-30"},
        {**row, "receipt_date": "2026-08-05", "new_receipt_date": "2026-08-06"},
        {**row, "receipt_date": UNKNOWN, "new_receipt_date": "2026-01-01"},
    ]
    sample = pd.DataFrame(rows)
    for field in FIELDS:
        if f"new_{field}" not in sample:
            sample[f"new_{field}"] = ""
    return sample


def test_breakdown_puts_blank_in_blank_column_and_excludes_unknown():
    counts = breakdown(_sample(), lambda f: f"new_{f}")["receipt_date"]
    assert counts == {"correct": 1, "wrong": 1, "blank": 1, "unknown": 1}


def test_breakdown_reconciles_with_score():
    sample = _sample()
    correct, compared, unknown = score(sample, lambda f: f"new_{f}")["receipt_date"]
    counts = breakdown(sample, lambda f: f"new_{f}")["receipt_date"]
    assert counts["correct"] == correct
    assert counts["correct"] + counts["wrong"] + counts["blank"] == compared
    assert counts["unknown"] == unknown
