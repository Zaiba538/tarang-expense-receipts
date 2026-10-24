# Photo-verified field evaluation

Sample: 52 receipt photos read directly from the images (`audit/photo_field_truth.csv`): 30 drawn at random within each layout family and 22 chosen deliberately as difficult or changed cases. Clerk values are compared only for sampled images that belong to training claims.

## Sample composition

| Layout family | Images | Random | Forced (difficult or changed) |
|---|---|---|---|
| cab_receipt | 7 | 3 | 4 |
| courier | 7 | 3 | 4 |
| fuel_pump_slip | 5 | 4 | 1 |
| handwritten_bill | 6 | 3 | 3 |
| hotel_invoice | 3 | 3 | 0 |
| no_text | 3 | 3 | 0 |
| other | 6 | 3 | 3 |
| parking_ticket | 6 | 4 | 2 |
| restaurant_tax_invoice | 9 | 4 | 5 |

## Photo-verified results, whole sample (difficult cases over-represented)

| Field | Unknown in photo | Old extraction (ocr_extractions_v3.csv) | New extraction (ocr_extractions_v4.csv) | Clerk entry vs photo (training claims only) |
|---|---|---|---|---|
| vendor | 3 | 49/49 (100%) | 49/49 (100%) | 28/33 (85%) |
| receipt_date | 6 | 43/46 (93%) | 46/46 (100%) | 31/32 (97%) |
| receipt_number | 4 | 47/48 (98%) | 47/48 (98%) | 29/33 (88%) |
| gstin | 4 | 47/48 (98%) | 47/48 (98%) | 29/33 (88%) |
| total_amount | 5 | 46/47 (98%) | 46/47 (98%) | 32/32 (100%) |

## Photo-verified results, random picks only

| Field | Unknown in photo | Old extraction (ocr_extractions_v3.csv) | New extraction (ocr_extractions_v4.csv) | Clerk entry vs photo (training claims only) |
|---|---|---|---|---|
| vendor | 3 | 27/27 (100%) | 27/27 (100%) | 15/17 (88%) |
| receipt_date | 4 | 26/26 (100%) | 26/26 (100%) | 16/17 (94%) |
| receipt_number | 3 | 27/27 (100%) | 27/27 (100%) | 15/17 (88%) |
| gstin | 3 | 27/27 (100%) | 27/27 (100%) | 16/17 (94%) |
| total_amount | 3 | 27/27 (100%) | 27/27 (100%) | 17/17 (100%) |

## New extraction (ocr_extractions_v4.csv) by outcome, whole sample

| Field | Compared with photo | Correct | Wrong (non-blank) | Blank (counted as a miss) | Unknown in photo (excluded) |
|---|---|---|---|---|---|
| vendor | 49 | 49 | 0 | 0 | 3 |
| receipt_date | 46 | 46 | 0 | 0 | 6 |
| receipt_number | 48 | 47 | 0 | 1 | 4 |
| gstin | 48 | 47 | 0 | 1 | 4 |
| total_amount | 47 | 46 | 0 | 1 | 5 |

## New extraction (ocr_extractions_v4.csv) by outcome, random picks only

| Field | Compared with photo | Correct | Wrong (non-blank) | Blank (counted as a miss) | Unknown in photo (excluded) |
|---|---|---|---|---|---|
| vendor | 27 | 27 | 0 | 0 | 3 |
| receipt_date | 26 | 26 | 0 | 0 | 4 |
| receipt_number | 27 | 27 | 0 | 0 | 3 |
| gstin | 27 | 27 | 0 | 0 | 3 |
| total_amount | 27 | 27 | 0 | 0 | 3 |

## New extraction disagreements with the photo

- **vendor** (0): none
- **receipt_date** (0): none
- **receipt_number** (1): img 459: photo `A/1774`, extracted `(blank)`
- **gstin** (1): img 122: photo `27HJXCW9975D1ZJ`, extracted `(blank)`
- **total_amount** (1): img 414: photo `315.00`, extracted `(blank)`

## Limitations

- The photo readings are an AI-assisted reading of each image; no named reviewer.
- GSTIN: printed O and 0 look alike; the PAN letter positions were recorded as letters, as the GSTIN format requires.
- Altered totals are recorded as displayed on the bill (with a note); detecting the alteration is a separate check.
- The sample is small and deliberately difficult; it does not estimate dataset-wide accuracy, and it does not show that the 95% field target is met across the dataset.
- Random picks were drawn in fixed numbers per layout family, not in proportion to the dataset, so the random-only table is not a dataset-wide accuracy estimate either.
- Processing coverage (all 467 images) is reported separately from this verified accuracy.
