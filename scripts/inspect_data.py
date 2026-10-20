
from pathlib import Path
import sys

import pandas as pd


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

CSV_FILES = [
    "claims_train.csv",
    "claims_test.csv",
    "employees.csv",
    "sample_submission.csv",
]


def find_csv(filename: str) -> Path | None:
    """Find a CSV in the data folder, including its subfolders."""
    direct_path = DATA_DIR / filename

    if direct_path.exists():
        return direct_path

    matches = list(DATA_DIR.rglob(filename))
    return matches[0] if matches else None


def inspect_dataframe(name: str, df: pd.DataFrame) -> None:
    """Print a useful overview of a dataset."""
    print("\n" + "=" * 75)
    print(f"DATASET: {name}")
    print("=" * 75)

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    print("\nColumn names and data types:")
    print(df.dtypes.to_string())

    print("\nFirst 5 rows:")
    print(df.head().to_string(index=False))

    print("\nMissing values:")
    missing = df.isna().sum()
    missing = missing[missing > 0]

    if missing.empty:
        print("No pandas-recognized missing values.")
    else:
        for column, count in missing.items():
            percentage = count / len(df) * 100 if len(df) else 0
            print(
                f"  {column}: {count:,} "
                f"({percentage:.2f}%)"
            )

    print("\nDuplicate rows:", int(df.duplicated().sum()))

    # Report duplicate identifiers where an ID column exists.
    id_columns = [
        column
        for column in df.columns
        if column.lower() in {
            "claim_id",
            "claimid",
            "employee_id",
            "emp_id",
        }
    ]

    for column in id_columns:
        duplicate_count = int(df[column].duplicated().sum())
        print(f"Duplicate values in {column}: {duplicate_count:,}")

    # Show the distributions of likely decision/label columns.
    label_columns = [
        column
        for column in df.columns
        if any(
            keyword in column.lower()
            for keyword in ("decision", "status", "outcome", "label")
        )
    ]

    for column in label_columns:
        print(f"\nValue counts for {column}:")
        print(df[column].value_counts(dropna=False).to_string())


def main() -> None:
    if not DATA_DIR.exists():
        print(f"ERROR: Data folder not found: {DATA_DIR}")
        sys.exit(1)

    print("=" * 75)
    print("TARANG PHARMA DISTRIBUTION")
    print("EXPENSE RECEIPT DATA INSPECTION")
    print("=" * 75)
    print(f"Project directory: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}")

    found_any = False

    for filename in CSV_FILES:
        path = find_csv(filename)

        if path is None:
            print(f"\nNOT FOUND: {filename}")
            continue

        found_any = True

        try:
            # Read identifiers as strings to preserve leading zeros.
            df = pd.read_csv(path, dtype=str)

            print(f"\nFile: {path.relative_to(PROJECT_ROOT)}")
            inspect_dataframe(filename, df)

        except Exception as exc:
            print(f"\nERROR reading {filename}: {exc}")

    if not found_any:
        print(
            "\nNo expected CSV files were found.\n"
            "Place the assignment CSVs in the data/ folder.\n"
            "Expected names: claims_train.csv, claims_test.csv,\n"
            "employees.csv and sample_submission.csv."
        )
        sys.exit(1)

    print("\n" + "=" * 75)
    print("DATA INSPECTION FINISHED")
    print("=" * 75)


if __name__ == "__main__":
    main()
