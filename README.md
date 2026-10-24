# Tarang Pharma Expense Receipt Review

Reads receipt photos with local OCR, checks each claim against its bill, the expense policy and other claims, and recommends **approve** (every available check passed) or **review** (a clerk must look). It supports a clerk; it does not replace policy or human judgement. No API key or paid service is needed.

## 1. Setup (Windows, Python 3.11)

```powershell
cd C:\path\to\tarang-expense-receipts
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` includes PaddleOCR and PaddlePaddle (CPU). The OCR models download on first use (about 180 MB, cached in `%USERPROFILE%\.paddlex`). Copy `.env.example` to `.env` if you want to change `APP_ENV` or `LOG_LEVEL`; nothing else is configured.

The receipt photos are not in the repository (they are git-ignored). Place them in `tarang-expense-receipts\images\` (`manifest.csv` lists the expected files and SHA-256 hashes).

## 2. Run the API (FastAPI)

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- `GET /health` returns `{"status": "ok"}`; interactive docs at `http://127.0.0.1:8000/docs`.
- `POST /review` (form data): `photo` (JPG/PNG/WEBP, max 10 MB), `claim_id`, `employee_id`, `category`, `amount_claimed`, optional `receipt_date`. Returns the extracted fields, `decision`, `reason`, `employee_found` and `limitations`. This single-photo endpoint does not compare against other claims (duplicates, colleague vehicles, parking overlaps); those checks run in the batch pipeline. A key field read only by the enhanced second OCR pass sends the claim to review: a recovered value is confirmed by a person, never approved on its own.
- `POST /decide` (JSON): decide on receipt fields you supply.

Example (PowerShell, image 011 is a parking ticket):

```powershell
$img = (Get-ChildItem .\tarang-expense-receipts\images\011_*.jpg).FullName
curl.exe -s -X POST http://127.0.0.1:8000/review -F "photo=@$img;type=image/jpeg" -F "claim_id=SMOKE-1" -F "employee_id=TPD-0431" -F "category=Parking" -F "amount_claimed=30"
```

The first `/review` call is slow while the OCR models load.

## 3. Run the screen (Streamlit)

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui\streamlit_app.py --server.port 8501
```

Open `http://localhost:8501`: upload a photo, enter the claim details, **Extract receipt fields**, correct any field, then **Evaluate claim**. Uploading a different photo clears the previous receipt's fields and result (matched by file content).

## 4. Batch pipeline (reproduces the deliverables)

```powershell
# Fresh OCR text + fields for every photo, resumable (about 10 s per photo on a laptop CPU).
# Writes reports\ocr_extractions_fresh.csv; repeat until it prints "remaining: 0".
.\.venv\Scripts\python.exe -B scripts\extract_receipts.py --resume --limit 40
# Re-apply the current field rules to that OCR text, both passes (seconds); this builds the v4 file used by predictions
.\.venv\Scripts\python.exe scripts\reextract_from_raw_text.py --input reports\ocr_extractions_fresh.csv --output reports\ocr_extractions_v4.csv
.\.venv\Scripts\python.exe scripts\generate_predictions.py     # predictions.csv (190 test claims)
.\.venv\Scripts\python.exe scripts\build_audit_ledger.py       # reports\audit_exposure_ledger.csv
.\.venv\Scripts\python.exe scripts\evaluate_photo_truth.py     # reports\photo_field_evaluation.md
.\.venv\Scripts\python.exe scripts\evaluate_fields.py          # agreement with clerk entries
.\.venv\Scripts\python.exe scripts\evaluate.py                 # training decisions vs historical status
```

**`predictions.csv`, the audit ledger and the evaluation reports are generated from `reports/ocr_extractions_v4.csv`**: the fresh full OCR run of all 467 photos (`reports/ocr_extractions_fresh.csv`, run in resumable batches after an earlier attempt stopped at 10 photos for lack of memory), re-extracted with the current field rules. The raw fresh file is never used directly: its fields predate the current rules, and the prediction and ledger scripts refuse it.

The fresh run's first-pass OCR text is identical to the stored text for every photo. Its enhanced second pass ran on 12 photos; v4 differs from v3 only where that pass filled a blank: dates on 275, 417 and 459, totals on 388 and 444, bill number on 462 and vehicle numbers on 388 and 456. Each matches its photo (`audit/photo_field_truth.csv`, `audit/photo_checks_followup.csv`); on 388 the amount in words is scribbled over, so the ₹1,100 figure is probable, not confirmed. Claims whose key field came only from the second pass stay in review, so approvals are unchanged (80 approve, 110 review). When the second pass filled the total, the bill's own figures are checked on that pass (this cleared a false warning on 444, where the first pass misread "60" as "09"); every photo-identified altered total is still flagged.

Earlier extraction files are kept as records: `ocr_extractions.csv` (original OCR run), `ocr_extractions_v2.csv` and `ocr_extractions_v3.csv` (stored first-pass text only).

## 5. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

When re-run on 25 October 2026: 208 tests passed (extraction rules, normalization, duplicate and parking checks, integrity checks, decisions, policy, audit ledger, resumable OCR checkpointing, API and Streamlit screen; OCR is stubbed in the UI and resume tests).

## 6. Outputs and evidence

| File | What it is |
|---|---|
| `predictions.csv` | 190 test claims in the `sample_submission.csv` format: 80 approve, 110 review |
| `memo-to-nilesh.md` | Findings, costs and the recommended pilot |
| `reports/ocr_extractions_v4.csv` | Fields, amount in words, route/km, fuel rate/volume and raw OCR text (both passes) for all 467 photos |
| `audit/photo_field_truth.csv` | 52 photos read by eye (30 random within layout families, 22 chosen as difficult) |
| `reports/photo_field_evaluation.md` | Extraction vs those photos: vendor 49/49, date 46/46, number 47/48, GSTIN 47/48, total 46/47; all misses are blanks, shown apart from wrong values |
| `audit/photo_review_findings.csv` | 47 photo-reviewed findings (altered totals, duplicates, colleague vehicles, printed instructions) |
| `reports/audit_exposure_ledger.csv` | Every finding, its evidence category and potential exposure, each claim counted once |
| `reports/field_evaluation_summary.txt` | Agreement with clerk-typed fields on 283 training claims (not accuracy: clerk entries can be wrong) |
| `reports/evaluation_summary.txt` | Training decisions vs historical status: 127/283 agree (44.9%); historical approvals are not proof of policy compliance |
| `reports/v2_regeneration_change_report.md` | Every change to extraction and predictions, traced |

`reports/evaluation.md` and `reports/error_analysis.md` describe an earlier version and are kept for history.

## 7. Limitations

- The photo-checked sample is 52 photos and deliberately difficult; it is not a dataset-wide accuracy figure. Blank fields go to review; they are never guessed.
- Who paid a bill, fuel field days, driver's receipts, courier purpose and lodging eligibility cannot be established from the data, so those claims go to review.
- Duplicate, altered-total, colleague-vehicle and parking findings are evidence for a reviewer, not findings of misconduct.
- The same photo can OCR differently after re-compression (seen on image 051); figures confirmed by the bill's amount in words are the most reliable.

## 8. Security

Do not commit `.env`, API keys, passwords, signed download URLs or private employee data. `.env`, the virtual environment, caches, backups and the receipt photos are git-ignored.
