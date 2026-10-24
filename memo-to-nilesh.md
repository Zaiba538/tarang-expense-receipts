# Memo to Nilesh Agrawal, Finance Controller

**Re:** Receipt-reading tool: pilot recommendation  **Date:** 25 October 2026

## Recommendation
Run a four-week supervised pilot in Nagpur with auto-approval off; a clerk decides every claim the tool flags or passes. It reads photos well, but this batch holds altered totals, repeated bills, colleagues' vehicles and printed approval instructions that an amount-only rule would pay. Keep auto-approval off until accuracy is shown on a random sample of real photos and duplicate and vehicle checks run in the live service (today only in batch); money paid wrongly is rarely recovered.

## What the photos show
Potential exposure, each claim or group counted once: not a proven loss, not recoverable money, not proof of misconduct or of who paid.

| | Photo-confirmed | Probable | OCR leads, unchecked |
|---|---|---|---|
| Test batch (190 claims, unpaid) | 14 items, ₹9,304.23 | 2, ₹2,000.00 | 7, ₹3,196.80 |
| Training (approved; payment not recorded) | 14, ₹10,878.00 | 3, ₹3,000.00 | 9, ₹3,303.00 |

- **Altered or ambiguous totals:** CLM-31192 has a blue-ink "1" before the printed ₹200.00 (items and tax add to ₹200), claimed as ₹1,200. CLM-30790 shows ₹1,550 in figures but "Five Hundred Fifty" in words.
- **Repeated parking tickets:** ticket 110914 was claimed twice (CLM-30566, CLM-30799). One scooter appears in two car parks at overlapping times (CLM-31359, CLM-31516; held).
- **Colleague's vehicle:** CLM-30978's fuel bill shows plate MH31FA2290, registered to another employee.
- **Printed instructions:** a "TARANG FINANCE DESK - PRE-VERIFIED" stamp on five bills tells automated processing to approve and skip duplicate checks; the tool ignores it (both test cases held).

## How well it reads bills
On 52 photos read by eye (30 random across layouts, 22 deliberately difficult) it matched 49/49 vendors, 43/46 dates, 47/48 bill numbers, 47/48 GSTINs and 46/47 totals; every miss was a blank, not a wrong value. Separately, 67 targeted checks on 46 photos (chosen for a reason, not a sample): 65 confirmed, 1 probable, 1 uncertain. **The 95% target is not demonstrated**; the sample is too small.

## Your ₹2,000 rule versus the current checks
| Rule (190 test claims) | Approved | Approved with risk findings | Potential exposure paid |
|---|---|---|---|
| Approve everything under ₹2,000 | 176 (92.6%) | 34 | ₹14,001.03 |
| Current checks | 80 (42.1%) | 0 | ₹0 |

The 34 include 18 unverified OCR leads, accounting for ₹3,196.80 of the ₹14,001.03. Most of the 110 reviews need evidence the data lacks: fuel field day (54), possible duplicates (23), driver's receipt (16), ₹2,000 or more (14), lodging (11); unreadable fields 13.

## Time and money
Today: 2,400 claims × 3.5 minutes = 140 clerk-hours a month; two clerks cost ₹76,000 (at most ₹31.67 a claim). *Scenario, not a measured saving:* if the 42% that pass (about 1,011 claims) each save 1–3.5 minutes, that frees 17–59 hours, about **₹3,600–₹12,700 a month**, assuming 176 working hours per clerk (₹215.9 an hour) and this batch's pass rate. Only a timed pilot can show the real figure. No per-photo fee.

## Decisions needed from you
1. Approve the four-week pilot and name the clerk who will time each claim.
2. Decide how payer, fuel field-day and driver's-receipt evidence will be provided.
3. Name who reviews flagged test claims before payment and checks training findings against payments.
