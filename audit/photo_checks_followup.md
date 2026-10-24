# Follow-up photo checks (2026-10-24)

`audit/photo_checks_followup.csv` records 67 photo checks on 46 receipt images,
made during the follow-up review of 24 October 2026. Each row is one check of
one field or risk on one image. No script reads this file: it does not change
any metric, the exposure ledger or `predictions.csv`.

## How the checks were made, and when

All 67 rows are **observations carried forward** from earlier stages of the
2026-10-24 review. Each image was opened at the stage named in
`inspection_stage`; **none was re-inspected when this file was written**
(Phase 2 opened no images).

| `inspection_stage` | Images opened at that stage | Why |
|---|---|---|
| `date_followup` | 087, 088, 101, 109, 110, 116, 117, 119, 121, 130, 327, 328, 334, 373, 375, 405, 440, 441, 465 | Check the dates behind new approvals; plates and in/out times were read on the same tickets |
| `approval_check` | 379 | Claim CLM-31251 moved to approve |
| `fresh_ocr_second_pass` | 388, 444, 462 | Values filled only by the enhanced second OCR pass |
| `receipt_050_review` | 050 | Vehicle number missed by OCR |
| `extraction_audit` | 008, 027, 038, 063, 098, 180, 187, 192, 250, 252, 262, 292, 367, 399, 456 | Values changed by the dataset-wide extraction rules |
| `phase1_plan` | 274, 430 (first opened here), 063 (opened again) | Plates not checked before (see Corrections) |
| `parking_investigation` | 175, 181, 247, 270, 303 | Same-vehicle parking conflicts and the repeated ticket |

Images 405 and 465 were not reopened for the parking investigation: their
times were read during `date_followup`.

Photos were read by an AI assistant (Claude Code) acting as a single reviewer;
no person is recorded as having checked them, and the checks are not
independent.

## Columns

`compared_value` is the value the photo was compared with, from
`compared_source`: mostly `reports/ocr_extractions_v3.csv` at commit `88643c6`
(the file `predictions.csv` uses); the fresh OCR file for second-pass values;
the extraction rules at `3b1ee3d` applied to the fresh OCR text for plates
recovered only from the second pass (388, 456); and the exposure ledger for
duplicate and parking findings.

| `outcome` | Meaning |
|---|---|
| `match` | The photo shows the compared value |
| `blank_correct` | The extraction is blank, and the old non-blank value was wrong |
| `blank_unresolved` | The extraction is blank although the photo is readable |
| `cannot_confirm` | The photo cannot settle the value |

| `confidence` | Meaning |
|---|---|
| `confirmed` | Legible on the photo and unambiguous |
| `probable` | Legible, but other evidence on the bill cannot corroborate it |
| `uncertain` | Partly illegible; more than one reading is possible |
| `unreadable` | Not legible (no such rows here) |

`exposure_note` points to potential exposure already in
`reports/audit_exposure_ledger.csv`. Nothing here is a confirmed loss,
payment or recovery, and no new amount is calculated.

## Results

- 65 checks confirmed, 1 probable, 1 uncertain.
- 63 matches, 2 old values correctly blanked (187, 192), 1 readable plate still
  blank in the extraction (181), 1 cannot be confirmed (063).

## Uncertainties

- **063 (CLM-30925, fuel), plate:** `uncertain`. The print is motion-blurred.
  The extraction reads `MH34BT9842`; the claimant TPD-0459 is registered as
  `MH34 BT 9042`. The series letters agree, but one digit differs. The photo
  cannot show whether OCR misread 0 as 8 or this is a different vehicle. The
  claim is labelled vehicle-uncertain and stays in review.
- **388 (CLM-31244), total:** `probable`. The figure reads `1100/-`, but the
  amount in words is scribbled over and cannot corroborate it.

## Corrections

- An earlier report in this review said images 274 and 430 had already been
  checked. That was wrong: 274 had not been opened, and 430's plate had not
  been recorded. Both were opened during the Phase 1 plan, and both plates
  match (274 `MH31EK4471`, 430 `MH31DX0981`).

## Evidence referenced, not repeated

- `audit/photo_field_truth.csv`: the 52-photo field sample used for accuracy
  figures, including the dates on images 275, 417 and 459. Rows here cover
  only fields or risks that sample does not record (for example the plates
  on 008 and 430, and the duplicate ticket on 175).
- `audit/photo_review_findings.csv`: the 47 findings used by the ledger
  (for example 050's altered total and the 399/456 duplicate bill).

## Limitations

- These checks are targeted (images opened for a reason), not a random
  sample, so they say nothing about dataset-wide accuracy.
- "Confirmed" means the photo is legible and agrees. It is not proof of
  payment, misuse or loss.

## Tracing a row

`image_filename` is the file in `tarang-expense-receipts/images/`; `claim_id`
and `split` come from `data/Task 2 Files/claims_train.csv` or `claims_test.csv`
(matched by image filename).
