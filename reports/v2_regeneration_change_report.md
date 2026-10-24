# Predictions and audit ledger regenerated from v2 extractions

Date: 2026-10-24. Inputs: `reports/ocr_extractions_v2.csv` (fields re-extracted
from the stored OCR text; raw text identical to `reports/ocr_extractions.csv`).
Decision, policy, integrity, duplicate-detection and extraction code unchanged.
Backups of the previous outputs: `backups/pre_v2_regen_2026-10-24/`.

## Reproducibility

- The previous ledger rebuilds byte-identically from the old OCR file.
- The previous `predictions.csv` rebuilds identically from the old OCR file except
  one reason text (CLM-31478, still review): the approved plausible-year rule now
  rejects its OCR date "2826-08-05", so "receipt date missing or unreadable" is added.
- Both v2 outputs were generated twice and are byte-identical between runs.

## Test decisions (190 claims)

| | Old | New |
|---|---|---|
| approve | 59 | 80 |
| review | 131 | 110 |

21 claims moved from review to approve; none moved from approve to review.
Each was in review only because its receipt date was blank; v2 filled the date,
and the filled date equals the claimed expense date in all 21.

| Claim | Image | Category | Date source |
|---|---|---|---|
| CLM-31087, CLM-31106, CLM-31340 | 328, 334, 110 | Food | labelled `Date: dd-Mon-yy` |
| CLM-31088, CLM-31490 | 327, 130 | Food | only date on the bill, unlabelled |
| CLM-31111, 31112, 31152, 31222, 31255, 31256, 31314, 31359, 31407, 31411, 31423, 31424, 31428, 31516, 31519, 31523 | various | Parking | in/out times on the same, only date, unlabelled |

Claimed amounts of the 21: Rs 2,298 in total (food Rs 1,848; parking Rs 450).
Only 2 of the 21 (CLM-31152 image 353, CLM-31428 image 430) are in the photo-verified
sample; both dates agree with the photo. The other 19 dates (CLM-31087, 31088, 31106,
31111, 31112, 31222, 31255, 31256, 31314, 31340, 31359, 31407, 31411, 31423, 31424,
31490, 31516, 31519, 31523) were checked against their photos in a follow-up review
on 2026-10-24, and every date matched. That review is recorded only in this report:
its readings were not added to `audit/photo_field_truth.csv`, so these 19 checks are
not in a project audit file. Two of the 19 (CLM-31359, CLM-31516) are now in review
for a parking time conflict (see the update below).
"Approve" means the automated checks passed; it does not establish that a claim
is valid.

Reason text changed without a decision change for 5 claims:
- CLM-31176: date now read; duplicate reason adds "and bill date"; date warning removed.
- CLM-31178: date now read; date warning removed (still review: driver receipt).
- CLM-31454, CLM-31457: possible cross-employee duplicate removed (see below);
  both still review (fuel field-day check).
- CLM-31478: date "2826-08-05" now rejected as implausible and left blank.

## Extracted fields, claims with a photo (467: 280 training, 187 test)

| Field | Training | Test |
|---|---|---|
| vendor | 50 changed (oil-company logo to station name) | 38 changed (same) |
| receipt_date | 46 filled | 23 filled, 1 blanked (CLM-31478) |
| gstin | 25 filled (checksum-valid) | 18 filled, 1 blanked (CLM-31506, checksum failed) |

Receipt number and total amount are unchanged for every claim.

## Duplicate matches

- Removed: CLM-31454 / CLM-31457 ("possible" cross-employee match). The old match
  rested on both vendors being read as the logo "HPCL". The bills are from
  different stations (New Highway Service Station, Badnera Road, Amravati;
  Om Sai Fuel Point, Wadi, Nagpur) with different receipt numbers and vehicles.
  It carried no counted exposure.
- New matches: none. Match type changed: none. Claims flagged as duplicates: 60 before and after.
- 7 training and 1 test duplicate reasons now add "and bill date" because both dates are now read.

## Audit ledger

Rows: 519 to 538 (2 removed `duplicate_possible` OCR leads for the pair above;
21 added `policy_payer_identity` questions, one for each new approval, as for every
approved test claim). No other existing row changed in any column.

| Split | Category | Old rows | New rows |
|---|---|---|---|
| test | ocr_lead | 40 | 38 |
| test | policy_question | 172 | 193 |
| all other split/category pairs | | unchanged | unchanged |

Counted exposure is unchanged in every split, category and measure:
test Rs 14,501.03 (potential; unpaid test claims), training Rs 17,181.00
(payments are not recorded in the data). These are evidence-based exposure
figures, not amounts paid or recoverable.

## Checks

- predictions: 190 rows, required columns, IDs and order match `sample_submission.csv`,
  no duplicate IDs, decisions only approve/review.
- ledger: same columns; finding IDs unique; every claim ID exists; 49 counted rows,
  no claim or payer-unknown group counted twice, no member of a counted payer-unknown
  group counted separately; every counted row is open; test decision context matches
  the new predictions.

## Not yet updated

The memo and other reports still describe the old predictions (59 approvals).

## Update: same-vehicle parking time check (2026-10-24)

Duplicate detection now also compares parking tickets: the same registered
vehicle at two different car parks with overlapping entry-exit times on one
date sends both claims to review (flag `parking_time_conflict`; not a
duplicate bill). Times, date and plate must all be read from the ticket;
otherwise the ticket is treated as uncertain and not matched. Backups of the
outputs before this change: `backups/pre_parking_check_2026-10-24/`.

| | Before | After |
|---|---|---|
| approve | 80 | 78 |
| review | 110 | 112 |

- CLM-31359 and CLM-31516 (TPD-0412, vehicle MH31EK4471, 1 Aug 2026; Medical
  Square 10:07-14:42 and Sitabuldi 09:28-13:37; Rs 20 and Rs 30): approve to review.
  No other prediction changed in any column.
- Ledger: 538 to 540 rows. Added four uncounted `parking_time_conflict` OCR leads
  (the pair above, and training pair CLM-30872 / CLM-31007, TPD-0431, MH31DX0981,
  2 Jul 2026, both historically approved, payment not recorded); removed the two
  payer-identity questions for the claims no longer approved. No amount is attached,
  and counted exposure is unchanged. All four tickets were opened on their photos
  in the parking investigation; the photo-review fixture was not changed, so the
  ledger still labels them OCR leads.
- The identical-ticket pair CLM-30566 / CLM-30799 (Sitabuldi ticket 110914) was
  already matched as `same_bill` (duplicate group DG-013) and is unchanged.
- The memo was updated for the current approval figures and the new check.

## Update: OCR v3 from stored OCR text (2026-10-24)

`reports/ocr_extractions_v3.csv` re-applies improved field rules to the stored
OCR text of all 467 images (`scripts/reextract_from_raw_text.py`). A fresh full
OCR run with the new enhanced second pass was first attempted at this point but
stopped at 10 images because the machine ran low on memory (it was completed
later; see the next section). v3 uses the stored first-pass text only; the
second pass (`raw_text_enhanced`) is empty for every row.

Rule changes: a handwritten total that OCR misread ('1230/-' as '12307-') is
accepted only when the bill's own amount in words matches one reading; a figure
split by OCR ('Amount Rs. 1' beside '940/-') is left blank; label and date
misreads ('Redeipt', 'AMB', '24-06-202616:24', '25/712026') are read when exactly
one value fits. Amount in words, route, km and fuel rate/volume are new columns.

| Field (of 467) | v2 | v3 |
|---|---|---|
| receipt_date | 454 | 459 |
| receipt_number | 460 | 462 |
| total_amount | 448 | 456 |
| vendor / gstin / vehicle_no | 464 / 207 / 192 | unchanged |

16 blanks were filled (images 012, 027, 051, 102, 122, 137, 218, 285, 301, 348,
370, 379, 398, 407, 426) and one wrong value removed (191: '1.00' to blank). No
other value changed. Contradictions flagged, not corrected: 050 (figure 1550,
words 550), 425 (1390 vs 390), 191 (figure unreadable, words 940).

Predictions: 78 to 80 approvals. CLM-31251 (image 379) and CLM-31506 (image 122)
moved to approve because their date and AWB number are now read. Both photos
were opened: 122 is in the photo-truth sample; 379 was checked on 2026-10-24
(SPEEDLINK COURIERS, 28-07-2026, AWB SL59393970, GSTIN 27HJXCW9975D1ZJ,
Rs 141.60, all matching) and is recorded here only, not in an audit file.
Six other test claims changed reason text only. Counted ledger exposure is
unchanged; the ledger has 533 rows. Backups: `backups/pre_v3_2026-10-24/`.

## Update: fresh full OCR run completed (2026-10-24)

`scripts/extract_receipts.py --resume` re-ran OCR on the photos one at a time,
writing each result to `reports/ocr_extractions_fresh.csv` before the next and
skipping photos already saved. The 10 photos from the interrupted attempt were
kept (not re-run); the other 457 were processed in 11 batches. Result: 467 rows
for the same 467 photos, no duplicates, no missing photos and no OCR failures.

- The first-pass OCR text is identical to the stored OCR text for all 467 photos.
- The enhanced second pass ran on 12 photos whose date, number or total was
  blank, and filled 6 fields that are blank in v3: dates on 275 (2026-07-01),
  417 (2026-07-30) and 459 (2026-08-05); totals on 388 (Rs 1,100) and 444
  (Rs 245); bill number on 462 (8354). No value read in v3 changed.
- All 6 match the photos. The three dates are confirmed by
  `audit/photo_field_truth.csv`; 388, 444 and 462 were checked by opening the
  photos and are recorded here only. On 388 the amount in words is scribbled
  over, so it cannot confirm the Rs 1,100 figure.
- Against the 52-photo sample, dates rise from 43/46 to 46/46; vendor, number,
  GSTIN and total are unchanged, with no wrong values.

`predictions.csv`, the audit ledger and the evaluation reports were **not**
regenerated: they still use `ocr_extractions_v3.csv` (190 test claims, 80
approve, 110 review, every reason filled). Using the fresh file would need them
regenerated and every changed decision traced. The latest recorded test run was
183 passed; tests were not re-run for this documentation update.
