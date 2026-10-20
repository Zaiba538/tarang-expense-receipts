
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = PROJECT_ROOT / "reports"

CLAIM_FILES = ["claims_train.csv", "claims_test.csv"]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
EXCLUDED_DIRS = {".venv", "venv", "node_modules", ".git", "__pycache__"}


def find_file(filename: str) -> Path | None:
    """Find an assignment file anywhere inside data/."""
    matches = list(DATA_DIR.rglob(filename))
    return matches[0] if matches else None


def normalize_filename(filename: str) -> str:
    """Normalize a filename for case-insensitive comparison."""
    return Path(str(filename).replace("\\", "/").strip()).name.lower()


def filename_matches(actual_name: str, expected_name: str) -> bool:
    """Match filenames with UUID prefixes and equivalent jpg/jpeg extensions."""
    actual = normalize_filename(actual_name)
    expected = normalize_filename(expected_name)

    actual_path = Path(actual)
    expected_path = Path(expected)

    actual_stem = actual_path.stem
    expected_stem = expected_path.stem

    # Match the exact filename first.
    if actual == expected:
        return True

    # JPG and JPEG are equivalent extensions for matching purposes.
    equivalent_extensions = {".jpg", ".jpeg"}
    if (
        actual_stem == expected_stem
        and actual_path.suffix in equivalent_extensions
        and expected_path.suffix in equivalent_extensions
    ):
        return True

    # Match downloaded names that contain a UUID prefix.
    return (
        actual_stem.endswith("-" + expected_stem)
        and actual_path.suffix == expected_path.suffix
    ) or (
        actual_stem.endswith("-" + expected_stem)
        and actual_path.suffix in equivalent_extensions
        and expected_path.suffix in equivalent_extensions
    )


def index_images() -> list[Path]:
    """Find available receipt images in the project."""
    image_paths = []

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(part.lower() in EXCLUDED_DIRS for part in path.parts):
            continue

        if path.suffix.lower() in IMAGE_EXTENSIONS:
            image_paths.append(path)

    return image_paths


def find_matching_image(
    expected_name: str,
    image_paths: list[Path],
) -> tuple[Path | None, str]:
    """Match a claim to exactly one local image."""
    if not expected_name or pd.isna(expected_name):
        return None, "missing_image_filename"

    matches = [
        path
        for path in image_paths
        if filename_matches(path.name, expected_name)
    ]

    if len(matches) == 1:
        return matches[0], "matched"

    if len(matches) > 1:
        return None, "ambiguous_multiple_matches"

    return None, "image_not_found"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("TARANG PHARMA DISTRIBUTION - IMAGE MATCHING")
    print("=" * 72)

    image_paths = index_images()
    print(f"\nImage files found in project: {len(image_paths)}")

    reports = []

    for csv_name in CLAIM_FILES:
        csv_path = find_file(csv_name)

        if csv_path is None:
            print(f"\nCSV NOT FOUND: {csv_name}")
            continue

        df = pd.read_csv(csv_path, dtype=str)

        required_columns = {"claim_id", "image_file"}
        missing_columns = required_columns - set(df.columns)

        if missing_columns:
            print(
                f"\nCannot process {csv_name}. "
                f"Missing columns: {sorted(missing_columns)}"
            )
            continue

        rows = []

        for _, row in df.iterrows():
            expected_name = row["image_file"]

            matched_path, status = find_matching_image(
                expected_name,
                image_paths,
            )

            rows.append({
                "dataset": csv_name,
                "claim_id": row["claim_id"],
                "image_file": expected_name,
                "matched_path": (
                    str(matched_path.relative_to(PROJECT_ROOT))
                    if matched_path
                    else ""
                ),
                "match_status": status,
            })

        report = pd.DataFrame(rows)
        reports.append(report)

        counts = report["match_status"].value_counts()

        print(f"\nDataset: {csv_name}")
        print(f"Claims: {len(report)}")
        print(f"Matched images: {counts.get('matched', 0)}")
        print(f"Images not found: {counts.get('image_not_found', 0)}")
        print(
            "Ambiguous matches: "
            f"{counts.get('ambiguous_multiple_matches', 0)}"
        )
        print(
            "Missing filenames: "
            f"{counts.get('missing_image_filename', 0)}"
        )

        print("\nFirst 5 results:")
        print(report.head().to_string(index=False))

    if not reports:
        print("\nERROR: No claim datasets could be processed.")
        return

    combined = pd.concat(reports, ignore_index=True)
    output_path = REPORT_DIR / "image_match_report.csv"
    combined.to_csv(output_path, index=False)

    print("\n" + "=" * 72)
    print(f"Report saved to: {output_path}")
    print("=" * 72)

    if not image_paths:
        print(
            "\nNEXT ACTION: Download the receipt images into the project. "
            "No image-based predictions can be verified until the photos "
            "are available."
        )


if __name__ == "__main__":
    main()
