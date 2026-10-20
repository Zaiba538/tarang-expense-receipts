# Tarang Pharma Expense Receipt Review

## 1. Project Overview

This project extracts information from expense receipt images using Optical Character Recognition (OCR) and applies rule-based checks to support expense claim review.

The system produces two possible decisions:

- **Approve:** Available evidence passes the implemented checks.
- **Review:** Additional verification or human review is required.

The system supports reimbursement review; it does not replace company policy or human judgment.

## 2. Key Features

- OCR-based receipt field extraction.
- Vendor, date, receipt number, GSTIN, and amount normalization.
- Receipt validation and claim amount comparison.
- Expense policy checks for supported categories.
- Duplicate and possible-duplicate detection.
- FastAPI decision endpoint.
- Automated tests.
- Training evaluation and error analysis reports.
- CSV predictions matching the supplied submission format.

## 3. Project Structure

- `app/` — Application, extraction, validation, and decision logic.
- `data/` — Task data and data documentation.
- `images/` — Downloaded receipt images, if present.
- `reports/` — OCR, image matching, evaluation, and error analysis outputs.
- `scripts/` — Receipt extraction, image matching, evaluation, and prediction scripts.
- `tests/` — Automated tests.
- `ui/` — User interface files, if configured.
- `predictions.csv` — Generated test predictions.
- `requirements.txt` — Python dependencies.
- `Dockerfile` — Container build configuration.
- `docker-compose.yml` — Container orchestration configuration.

## 4. Requirements

Python 3.11 is recommended. Install the dependencies in the project's virtual environment.

```powershell
python -m pip install -r requirements.txt
```

PaddleOCR may require compatible PaddlePaddle and OCR model assets. Follow the official installation instructions if an OCR dependency is missing.

## 5. Extract Receipt Information

Run this command from the project root:

```powershell
python scripts/extract_receipts.py
```

The OCR extraction results are saved to `reports/ocr_extractions.csv`.

## 6. Match Receipt Images

```powershell
python scripts/match_images.py
```

Check `reports/image_match_report.csv` for missing or ambiguous image matches.

## 7. Generate Predictions

```powershell
python scripts/generate_predictions.py
```

This generates `predictions.csv` in the project root. The expected submission contains 190 test claims and the following columns:

`claim_id, vendor, receipt_date, receipt_number, gstin, total_amount, decision, reason`

Missing receipt fields should remain blank when they cannot be reliably extracted. Do not invent receipt information.

## 8. Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to access the interactive API documentation.

The health endpoint is available at `http://127.0.0.1:8000/health`.

## 9. Run Automated Tests

```powershell
python -m pytest -q
```

The previously recorded baseline was **56 passing tests**. Run the command again after code changes to verify the current project.

## 10. Evaluate Training Claims

```powershell
python scripts/evaluate.py
```

The evaluation generates:

- `reports/training_evaluation.csv`
- `reports/evaluation_summary.txt`

The recorded evaluation compared 283 training claims with historical statuses. It produced 88 agreements out of 283 claims, or 31.1%.

This is agreement with historical labels, not verified policy accuracy. The result indicates that the decision rules require further investigation.

## 11. Reports

- `reports/ocr_extractions.csv` — Extracted receipt fields.
- `reports/image_match_report.csv` — Receipt image matching results.
- `reports/training_evaluation.csv` — Claim-level historical-label comparison.
- `reports/evaluation.md` — Evaluation summary.
- `reports/error_analysis.md` — Disagreements and recommended investigation.

## 12. Important Limitations and Safeguards

- A missing or unreadable receipt should trigger clarification or review, not automatic rejection.
- Missing GSTIN alone is not automatically a policy violation for every expense category.
- Some policy requirements need evidence not present in the structured claim data.
- A possible duplicate is not proof of fraud.
- OCR results can contain errors and may require manual verification.
- Historical approvals do not prove compliance with the current policy.
- Final reimbursement decisions should follow company policy and appropriate human review.

## 13. Security

Do not commit API keys, passwords, signed download URLs, or private employee information. Keep `.env` out of version control and use environment variables for secrets.
