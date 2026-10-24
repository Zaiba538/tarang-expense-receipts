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
- `POST /review` (form data): `photo` (JPG/PNG/WEBP, max 10 MB), `claim_id`, `employee_id`, `category`, `amount_claimed`, optional `receipt_date`. Returns the extracted fields, `decision`, `reason`, `employee_found` and `limitations`. This single-photo endpoint does not compare against other claims (duplicates, colleague vehicles, parking overlaps); those checks run in the batch pipeline.
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
# Re-apply the current field rules to stored OCR text (seconds); this builds the v3 file used by predictions
.\.venv\Scripts\python.exe scripts\reextract_from_raw_text.py --input reports\ocr_extractions.csv --output reports\ocr_extractions_v3.csv
.\.venv\Scripts\python.exe scripts\generate_predictions.py     # predictions.csv (190 test claims)
.\.venv\Scripts\python.exe scripts\build_audit_ledger.py       # reports\audit_exposure_ledger.csv
.\.venv\Scripts\python.exe scripts\evaluate_photo_truth.py     # reports\photo_field_evaluation.md
.\.venv\Scripts\python.exe scripts\evaluate_fields.py          # agreement with clerk entries
.\.venv\Scripts\python.exe scripts\evaluate.py                 # training decisions vs historical status
```

**`predictions.csv`, the audit ledger and the evaluation reports are generated from `reports/ocr_extractions_v3.csv`**, which was built from stored OCR text (467 rows; the enhanced second OCR pass, `raw_text_enhanced`, is empty in v3).

**A fresh full OCR run of all 467 photos is complete in `reports/ocr_extractions_fresh.csv`** (467 rows, the same 467 images). It was run in resumable batches after an earlier attempt stopped at 10 photos for lack of memory. Its first-pass OCR text is identical to the stored text for every photo; its enhanced second pass ran on 12 photos and filled 6 more fields than v3 (dates on 275, 417 and 459; totals on 388 and 444; bill number on 462). All 6 match the photos: the three dates are confirmed by `audit/photo_field_truth.csv`; the other three were checked by opening the photos and are not in an audit file. On 388 the figure ₹1,100 matches the photo but the amount in words is scribbled over, so it cannot confirm the figure. **The fresh file is not yet used by `predictions.csv`.**

Earlier extraction files are kept as records: `ocr_extractions.csv` (original OCR run) and `ocr_extractions_v2.csv`.

## 5. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

When re-run on 25 October 2026: 191 tests passed (extraction rules, normalization, duplicate and parking checks, integrity checks, decisions, policy, audit ledger, resumable OCR checkpointing, API and Streamlit screen; OCR is stubbed in the UI and resume tests).

## 6. Outputs and evidence

| File | What it is |
|---|---|
| `predictions.csv` | 190 test claims in the `sample_submission.csv` format: 80 approve, 110 review |
| `memo-to-nilesh.md` | Findings, costs and the recommended pilot |
| `reports/ocr_extractions_v3.csv` | Fields, amount in words, route/km, fuel rate/volume and raw OCR text for all 467 photos |
| `audit/photo_field_truth.csv` | 52 photos read by eye (30 random within layout families, 22 chosen as difficult) |
| `reports/photo_field_evaluation.md` | Extraction vs those photos: vendor 49/49, date 43/46, number 47/48, GSTIN 47/48, total 46/47; all misses are blanks |
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
