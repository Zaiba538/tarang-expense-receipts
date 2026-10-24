# Error Analysis

> **Superseded (kept for history).** This analysis describes an earlier version. Current findings: `memo-to-nilesh.md`, `reports/audit_exposure_ledger.csv` and `reports/v2_regeneration_change_report.md`.

## Current Findings

The training evaluation covered 283 claims.

- Historical-label agreement: 88/283 (31.1%)
- Predicted approve: 80
- Predicted review: 203
- Historically approved but predicted review: 195
- Training receipt images matched: 280/283

Historical statuses are reference labels, not verified policy-compliance truth.

## Main Issue

The largest disagreement is that 195 historically approved claims were classified
as review. This requires investigation before changing the decision rules.

Possible causes include missing receipt fields, OCR errors, amount mismatches,
duplicate warnings, or policy requirements that cannot be verified from the data.
These are hypotheses, not confirmed explanations for every claim.

## Missing Images

Three training claims did not match a downloaded receipt image. A missing image
does not prove that a claim is invalid. Request a readable copy or route the
claim for manual review.

## Recommended Investigation

1. Open `reports/training_evaluation.csv`.
2. Filter historically approved claims predicted as review.
3. Group the results by category and decision reason.
4. Inspect the relevant receipt images and OCR output.
5. Verify the applicable policy condition before changing any rule.
6. Re-run automated tests and evaluation after justified changes.

## Safeguards

- Do not automatically reject claims because OCR is uncertain.
- Do not treat a possible duplicate as proven fraud without verification.
- Do not fabricate missing receipt fields.
- Do not claim historical-label agreement proves policy accuracy.
