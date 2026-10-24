# Memo

**To:** Nilesh Agrawal, Finance Controller  **Re:** Receipt-reading tool: findings, costs and safe use  **Date:** 24 October 2026

## Recommendation
Use the tool now to read bills and flag risky claims for a clerk. Do not switch on auto-approval under ₹2,000 yet: passing the automated checks is not enough, because the data cannot show who paid a bill, and the photos in this batch include altered totals, bills claimed twice and printed instructions telling software to approve. Run a four-week supervised pilot in Nagpur first (details below).

## What the tool does on this batch
- Reads vendor, bill date, bill number, GSTIN and total from all 467 photos; 3 photos have no readable text.
- On a photo-checked sample of 52 bills (30 random, 22 deliberately difficult), the extracted fields matched the photo for 49/49 vendors, 43/46 dates, 47/48 bill numbers, 47/48 GSTINs and 46/47 totals; every miss was a blank sent to review, not a wrong value. This is a small sample, not a measured accuracy for all bills, so the 95% target is not yet proven.
- Of the 190 new claims, 80 pass every check (54 food, 14 parking, 12 courier, all under ₹2,000) and 110 go to a clerk. Most reviews are policy evidence the data does not hold, not reading failures: fuel field day (54), possible duplicates (23), driver's receipt (16), ₹2,000 or more (14), lodging conditions (11); unreadable fields account for 13.

## Findings
Each claim, or duplicate group, is counted once. **The categories must not be added together.**

| Test: 190 unprocessed claims (potential exposure) | Items | Amount |
|---|---|---|
| Confirmed: claim exceeds what the bill supports (incl. totals altered in ink) | 8 | ₹5,470.23 |
| Confirmed: whole claim cannot be validly claimed* | 6 | ₹3,834.00 |
| Probable: bill contradicts itself; original bill needed | 2 | ₹2,000.00 |
| OCR leads, whole claims; photo check needed | 7 | ₹3,196.80 |

| Training: 283 processed (275 approved, 6 queried, 2 rejected); payment not recorded | Items | Amount |
|---|---|---|
| Confirmed: claim exceeds what the bill supports (incl. totals altered in ink) | 5 | ₹4,000.00 |
| Confirmed: whole claim cannot be validly claimed* | 9 | ₹6,878.00 |
| Probable: bill contradicts itself | 3 | ₹3,000.00 |
| OCR leads: excess / whole claims | 2 / 7 | ₹220.00 / ₹3,083.00 |

\*A bill already claimed, or fuel for a colleague's vehicle. Where different employees claimed one bill, one claim cannot be valid, but **which one, and who paid, is not established**.

Training figures are discrepancies on claims that were approved; your payment records would show what was actually paid. Nothing here is a finding of misconduct. Five bills carry a printed stamp ("TARANG FINANCE DESK - PRE-VERIFIED") telling automated processing to approve and skip duplicate checks; the tool treats this as untrusted text and the two in the test batch are held. Two pairs of parking tickets show one vehicle in two car parks at the same time: a test pair (CLM-31359, 31516), held, and a historically approved training pair (CLM-30872, 31007; ₹30 and ₹20). Which ticket is wrong is not established.

## Time and cost (policy v3.2 figures)
- **Today:** 2,400 claims × 3.5 minutes = 8,400 minutes = **140 clerk-hours a month**. Two clerks cost **₹76,000 a month**; spread over 2,400 claims that is at most **₹31.67 per claim** (the policy does not give clerk hours, so claim time cannot be priced more exactly). A query costs about ₹45 and delays the rep by a week.
- **Running the tool:** it reads bills locally with open-source OCR; no paid API, so no charge per photo. Reading took about 5–7 seconds per photo on a laptop CPU in our runs. Hosting and upkeep are not yet costed.
- **Savings are not measured.** The arithmetic to fill in during the pilot: every minute saved per claim across 2,400 claims frees 40 clerk-hours a month. Whether clerks save typing time on the 80-in-190 passed claims, and how long checking a flagged claim takes, must be timed, not assumed.
- **Why catching before payment matters:** the policy says money paid wrongly is rarely recovered, so holding the confirmed test claims above costs one review each, against the amounts shown.

## Pilot (four weeks, Nagpur, about 240 claims a month)
The tool reads and flags; clerks decide every claim. Record time per claim and whether each passed claim was correct. Switch on auto-approval for a category only if its passed claims prove correct and you have decided how the open evidence below is provided.

**Please decide:**
1. whether to run the pilot;
2. how payer identity, fuel field days, driver's receipts, courier purpose and lodging eligibility are evidenced (until then those claims stay with a clerk);
3. who checks the training findings against payment records and reviews the confirmed and probable test claims before payment.

*Assumptions and limits:* the field extraction behind these figures was rebuilt from the stored OCR text of all 467 photos; a fresh full OCR run of all 467 photos has since been completed separately (`reports/ocr_extractions_fresh.csv`): it read the same text and filled 6 more fields, all checked against the photos, but the claim decisions above do not use it yet; photo checks were AI-assisted with no named reviewer; 22 of the 80 passed claims have been checked against their photos (4 recorded in `audit/photo_field_truth.csv`, 18 in a follow-up review described in `reports/v2_regeneration_change_report.md`); the 95% field target and any savings are unproven until the pilot.
