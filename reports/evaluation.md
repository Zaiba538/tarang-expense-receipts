# Training Evaluation

## Purpose

This evaluation compares predicted decisions with historical statuses and compares extracted receipt fields with clerk-entered reference fields.

Historical statuses and clerk-entered fields are reference data, not independently verified ground truth. Agreement does not establish policy compliance or production readiness.

## Decision Evaluation

- Training claims: 283
- Claims matched to OCR images: 280
- Claims without OCR matches: 3
- Historical-label agreement: 88/283 (31.1%)
- Predicted approve: 80
- Predicted review: 203

### Interpretation

A total of 195 historically approved claims were predicted as review. This difference requires investigation and does not automatically mean those decisions are wrong. Historical approval does not prove that a claim satisfies every policy requirement.

Missing images and unreadable fields should trigger clarification or review, not an automatic fraud accusation.

## Receipt Field Evaluation

The following results measure agreement with clerk-entered reference fields among comparable records.

| Field | Correct | Incorrect | Comparable records | Agreement |
|---|---:|---:|---:|---:|
| Vendor | 159 | 118 | 277 | 57.40% |
| Receipt date | 222 | 7 | 229 | 96.94% |
| Receipt number | 244 | 14 | 258 | 94.57% |
| GSTIN | 86 | 5 | 91 | 94.51% |
| Amount | 237 | 22 | 259 | 91.51% |

Vendor extraction is the weakest evaluated field and requires additional review. Amount extraction also has errors that could affect claim decisions.

GSTIN agreement is based on only 91 comparable records; many records could not be compared because one or both values were missing. Missing GSTIN alone should not be treated as a policy violation when it is not required for the expense type.

These figures measure reference-field agreement, not independently verified OCR accuracy. The number of comparable records differs by field.

## Limitations and Risks

- Three training claims have no matched OCR image.
- OCR may misread vendor names, dates, receipt numbers, or amounts.
- Historical decisions may not reflect every applicable policy requirement.
- Missing evidence should lead to manual review or clarification where appropriate.
- These results alone do not establish production readiness or financial savings.

## Reproducibility

Run the following commands from the project root to regenerate the evaluation outputs:

python scripts/evaluate.py
python scripts/evaluate_fields.py


The scripts produce decision-evaluation and field-evaluation reports under reports/.
