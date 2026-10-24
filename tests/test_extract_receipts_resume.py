
"""Resumable OCR run: checkpointing, skipping saved images, separate failures."""

import csv

import pytest

import scripts.extract_receipts as batch


def ok_fields(name):
    return {"vendor": f"VENDOR {name}", "raw_text": f"text {name}", "readable": True, "errors": []}


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


@pytest.fixture
def images(tmp_path):
    folder = tmp_path / "images"
    folder.mkdir()
    paths = []
    for name in ("001_a.jpg", "002_b.jpg", "003_c.jpg", "004_d.jpg"):
        path = folder / name
        path.write_bytes(b"x")
        paths.append(path)
    return paths


def test_resume_skips_saved_images_and_logs_failures_separately(images, tmp_path, monkeypatch):
    output = tmp_path / "fresh.csv"
    failures = tmp_path / "fresh_failures.csv"
    calls = []
    failing = {"003_c.jpg"}

    def fake_extract(path):
        calls.append(path.name)
        if path.name in failing:
            return {"errors": ["ocr_processing_failed: MemoryError: out of memory"], "readable": False}
        return ok_fields(path.name)

    monkeypatch.setattr(batch, "extract_receipt_fields", fake_extract)

    batch.run_resumable(images, output, failures, limit=2)
    assert [row["image_filename"] for row in read(output)] == ["001_a.jpg", "002_b.jpg"]

    batch.run_resumable(images, output, failures, limit=None)
    assert calls == ["001_a.jpg", "002_b.jpg", "003_c.jpg", "004_d.jpg"]  # nothing redone
    saved = [row["image_filename"] for row in read(output)]
    assert saved == ["001_a.jpg", "002_b.jpg", "004_d.jpg"]  # the failure is not saved as OCR
    assert [row["image_filename"] for row in read(failures)] == ["003_c.jpg"]

    failing.clear()
    batch.run_resumable(images, output, failures, limit=None)
    saved = [row["image_filename"] for row in read(output)]
    assert sorted(saved) == ["001_a.jpg", "002_b.jpg", "003_c.jpg", "004_d.jpg"]
    assert len(saved) == len(set(saved))
    assert calls[-1] == "003_c.jpg"  # only the failed image was retried


def test_resume_refuses_a_checkpoint_with_duplicates(images, tmp_path):
    output = tmp_path / "fresh.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=batch.COLUMNS)
        writer.writeheader()
        for _ in range(2):
            writer.writerow(batch.csv_row("001_a.jpg", ok_fields("001_a.jpg")))

    with pytest.raises(SystemExit, match="duplicates"):
        batch.completed_images(output, {path.name for path in images})


def test_production_extraction_files_are_protected():
    names ={path.name for path in batch.PROTECTED_OUTPUTS}
    assert {"ocr_extractions.csv", "ocr_extractions_v2.csv", "ocr_extractions_v3.csv"} <= names
    assert batch.OUTPUT_CSV.name == "ocr_extractions_fresh.csv"
