
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "Task 2 Files"
REPORT_DIR = ROOT / "reports"

CLAIMS_FILE = DATA_DIR / "claims_train.csv"
OCR_FILE = REPORT_DIR / "ocr_extractions.csv"


# Actual reference columns in claims_train.csv.
# Actual OCR columns in ocr_extractions.csv.
FIELD_PAIRS = {
    "vendor": ("clerk_vendor", "ocr_vendor"),
    "receipt_date": ("clerk_bill_date", "ocr_receipt_date"),
    "receipt_number": ("clerk_bill_no", "ocr_receipt_number"),
    "gstin": ("clerk_gstin", "ocr_gstin"),
    "amount": ("clerk_bill_amount", "ocr_total_amount"),
}


def is_missing(value):
    return pd.isna(value) or str(value).strip() == ""


def normalize_text(value):
    if is_missing(value):
        return ""
    return " ".join(str(value).strip().lower().split())


def normalize_date(value):
    if is_missing(value):
        return ""

    value = str(value).strip()

    # Try common date formats explicitly first.
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ]

    for fmt in formats:
        parsed = pd.to_datetime(value, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%Y-%m-%d")

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return normalize_text(value)

    return parsed.strftime("%Y-%m-%d")


def compare_field(field, reference, extracted):
    if is_missing(reference) or is_missing(extracted):
        return None

    if field == "receipt_date":
        ref = normalize_date(reference)
        ext = normalize_date(extracted)
        return ref == ext if ref and ext else None

    if field == "receipt_number":
        ref = normalize_text(reference).replace(" ", "")
        ext = normalize_text(extracted).replace(" ", "")
        return ref == ext

    if field == "gstin":
        ref = normalize_text(reference).replace(" ", "").upper()
        ext = normalize_text(extracted).replace(" ", "").upper()
        return ref == ext

    if field == "amount":
        try:
            return abs(float(reference) - float(extracted)) <= 0.01
        except (TypeError, ValueError):
            return None

    return normalize_text(reference) == normalize_text(extracted)



def clean_image_filename(value):
    from pathlib import Path
    import re

    filename = str(value).strip().replace("\\", "/")
    filename = filename.rsplit("/", 1)[-1]

    # Remove the downloader's numeric and UUID prefix.
    filename = re.sub(
        r"^\d+_[0-9a-fA-F-]{36}-",
        "",
        filename
    )

    # Match the filename regardless of .jpg vs .jpeg.
    return Path(filename).stem.strip().lower()


def main():
    if not CLAIMS_FILE.exists():
        raise FileNotFoundError(f"Claims file not found: {CLAIMS_FILE}")

    if not OCR_FILE.exists():
        raise FileNotFoundError(f"OCR file not found: {OCR_FILE}")

    claims = pd.read_csv(CLAIMS_FILE, dtype=str)
    ocr = pd.read_csv(OCR_FILE, dtype=str)

    if "image_file" not in claims.columns:
        raise ValueError(
            f"claims_train.csv is missing image_file. "
            f"Columns: {claims.columns.tolist()}"
        )

    if "image_filename" not in ocr.columns:
        raise ValueError(
            f"ocr_extractions.csv is missing image_filename. "
            f"Columns: {ocr.columns.tolist()}"
        )

    # Validate reference fields.
    for reference_column, _ in FIELD_PAIRS.values():
        if reference_column not in claims.columns:
            raise ValueError(
                f"Missing reference column '{reference_column}'. "
                f"Available columns: {claims.columns.tolist()}"
            )

    # Rename every OCR field BEFORE merging, preventing vendor/date
    # and other shared column names from colliding.
    rename_map = {
        "vendor": "ocr_vendor",
        "receipt_date": "ocr_receipt_date",
        "receipt_number": "ocr_receipt_number",
        "gstin": "ocr_gstin",
        "total_amount": "ocr_total_amount",
    }

    for old_name in rename_map:
        if old_name not in ocr.columns:
            raise ValueError(
                f"OCR file is missing '{old_name}'. "
                f"Available columns: {ocr.columns.tolist()}"
            )

    ocr = ocr.rename(columns=rename_map)

    # Print the renamed columns so any future naming issue is visible.
    print("OCR columns after renaming:")
    print([
        column for column in ocr.columns
        if column.startswith("ocr_")
    ])

    claims["image_file"] = claims["image_file"].apply(clean_image_filename)
    ocr["image_file"] = ocr["image_filename"].apply(clean_image_filename)

    # Keep only fields required for evaluation.
    ocr_columns = [
        "image_file",
        "ocr_vendor",
        "ocr_receipt_date",
        "ocr_receipt_number",
        "ocr_gstin",
        "ocr_total_amount",
    ]
    ocr = ocr[ocr_columns].drop_duplicates(
        subset=["image_file"],
        keep="first",
    )

    # Prevent the merge from multiplying claim rows.
    merged = claims.merge(
        ocr,
        on="image_file",
        how="left",
        indicator=True,
        validate="many_to_one",
    )

    matched_count = int((merged["_merge"] == "both").sum())
    unmatched_count = int((merged["_merge"] == "left_only").sum())

    print(f"\nTraining claims: {len(claims)}")
    print(f"Unique OCR images: {len(ocr)}")
    print(f"Claims matched to OCR: {matched_count}")
    print(f"Claims without OCR match: {unmatched_count}")

    details = []
    summaries = []

    for field, (reference_column, ocr_column) in FIELD_PAIRS.items():
        correct = 0
        incorrect = 0
        missing_reference = 0
        missing_ocr = 0
        unmatched_images = 0

        for _, row in merged.iterrows():
            reference = row[reference_column]
            extracted = row[ocr_column]
            image_matched = row["_merge"] == "both"

            if is_missing(reference):
                missing_reference += 1

            if is_missing(extracted):
                missing_ocr += 1

            if not image_matched:
                unmatched_images += 1
                result = None
                status = "unmatched_image"
            else:
                result = compare_field(field, reference, extracted)

                if result is True:
                    correct += 1
                    status = "match"
                elif result is False:
                    incorrect += 1
                    status = "mismatch"
                else:
                    status = "not_comparable"

            details.append({
                "claim_id": row.get("claim_id", ""),
                "image_file": row["image_file"],
                "field": field,
                "reference_value": reference,
                "extracted_value": extracted,
                "match_status": status,
                "image_matched": image_matched,
            })

        comparable = correct + incorrect
        not_comparable = len(merged) - comparable
        accuracy = (
            round(correct / comparable * 100, 2)
            if comparable
            else 0.0
        )

        summaries.append({
            "field": field,
            "total_claims": len(merged),
            "image_matched_claims": matched_count,
            "unmatched_images": unmatched_images,
            "correct": correct,
            "incorrect": incorrect,
            "comparable": comparable,
            "not_comparable": not_comparable,
            "missing_reference": missing_reference,
            "missing_ocr": missing_ocr,
            "accuracy_percent": accuracy,
        })

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    details_path = REPORT_DIR / "field_evaluation.csv"
    summary_csv_path = REPORT_DIR / "field_evaluation_summary.csv"
    summary_txt_path = REPORT_DIR / "field_evaluation_summary.txt"

    pd.DataFrame(details).to_csv(details_path, index=False)

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(summary_csv_path, index=False)

    with summary_txt_path.open("w", encoding="utf-8") as file:
        file.write("Receipt OCR Field Evaluation\n")
        file.write("============================\n\n")
        file.write(f"Training claims: {len(claims)}\n")
        file.write(f"Unique OCR images: {len(ocr)}\n")
        file.write(f"Matched claims: {matched_count}\n")
        file.write(f"Unmatched claims: {unmatched_count}\n\n")
        file.write(summary_df.to_string(index=False))
        file.write("\n")

    print("\nField evaluation summary:")
    print(summary_df.to_string(index=False))

    print(f"\nDetailed results: {details_path}")
    print(f"CSV summary: {summary_csv_path}")
    print(f"Text summary: {summary_txt_path}")


if __name__ == "__main__":
    main()
