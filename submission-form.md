# Tarang Pharma Distribution — Submission Form

## 1. GitHub repository URL

**GitHub URL:** https://github.com/Zaiba538/tarang-expense-receipts

The repository contains the application code, tests, README, `memo-to-nilesh.md`, evidence reports, audit files and `predictions.csv` at the repository root.

## 2. What did you build, and what decision does it support for Nilesh? State the number and the rupees.

A receipt-review tool (FastAPI service, Streamlit screen and batch pipeline) that reads vendor, bill date, bill number, GSTIN and total from the photo with local OCR, then checks each claim against its own bill (including altered totals and the amount in words), the expense policy, and other claims (duplicate bills, colleague vehicles, one vehicle in two car parks at once, printed "approve this" instructions).

The decision it supports: **do not auto-approve under ₹2,000 yet; run a four-week supervised pilot.** In the 190 new claims it found, counted once per claim: 8 claims exceeding what the bill supports (₹5,470.23 potential exposure, photo-confirmed), 6 claims that cannot be validly claimed (₹3,834.00, photo-confirmed), 2 probable (₹2,000.00) and 7 OCR leads (₹3,196.80). These are potential exposures on unpaid claims, not losses or savings. Today's checking costs 140 clerk-hours a month (2,400 × 3.5 min) and ₹76,000 a month for two clerks, at most ₹31.67 per claim; the tool has no per-photo charge.

## 3. What do you expect predictions.csv to score on the hidden answers, field by field and on the approve/review decision, and why? Say how you estimated it.

Estimated from 52 receipt photos I read by eye (`audit/photo_field_truth.csv`; 30 random within layout families, 22 deliberately difficult), plus the blanks in `predictions.csv`:

- **Vendor:** about 97–98%. 49/49 photo-checked; 4 of 190 are blank (3 claims have no photo, 1 photo has no readable text).
- **Receipt date:** about 93–96%. 43/46 photo-checked (all 3 misses blank); 7 of 190 blank.
- **Receipt number:** about 95–97%. 47/48 photo-checked; 6 of 190 blank.
- **GSTIN:** about 95–98%. 47/48 photo-checked, checksum-validated; blank is correct for bills without a GSTIN.
- **Total amount:** about 93–96%. 46/47 photo-checked; 10 of 190 blank. Where a bill's total was altered in ink, I report the figure as displayed; if the hidden answer uses the original printed figure, those few will miss.

Every miss in the sample was a blank, never a wrong value, so the score is roughly the share of non-blank fields times a high read rate. The sample is small, so these are estimates, not measurements.

**Decision:** I expect lower agreement than on the fields. The tool sends 110 of 190 claims to review, many for policy evidence the data cannot show (fuel field day, driver's receipt, lodging conditions, payer), while on training claims Finance historically approved 275 of 283. On training claims my decisions agree with historical status on 127/283 (44.9%); historical approvals are not proof of compliance, and 14 training approvals have photo-confirmed problems.

## 4. How do you know it works? What did you measure it against, how did you get those answers, how many receipts, and what kinds of receipts does it get wrong?

- **Photos read by eye:** 52 receipts across 9 layouts (cab, courier, fuel, handwritten, hotel, no-text, parking, restaurant, other). Results in `reports/photo_field_evaluation.md`. A further 47 photo findings are recorded in `audit/photo_review_findings.csv`, and 19 bill dates of approved claims were checked in a follow-up review (`reports/v2_regeneration_change_report.md`).
- **Clerk entries** on 283 training claims, as agreement only (clerks are sometimes wrong: in the photo sample, clerk vendor was wrong on 5 of 33 bills).
- **183 automated tests** passed in the latest recorded run, including regression tests built from real OCR lines.

It gets wrong, by leaving blank: blurred or black photos (3 have no text), handwritten dates the OCR misses, totals whose handwritten "/-" OCR misreads when the amount in words is also unreadable, and a total label covered by a pen note. OCR also varies when the same photo is re-compressed. Every blank goes to review.

## 5. Did you change, narrow, or push back on Nilesh's ask? What, when, and why?

Yes. Nilesh asked for auto-approval of everything under ₹2,000. After reading the photos I recommended against switching it on now: in this batch, claims under ₹2,000 include totals altered in ink, the same bill claimed twice (sometimes by two employees), fuel for a colleague's vehicle, and bills printed with instructions telling software to approve and skip duplicate checks. A ₹2,000 threshold alone would pay all of these. I also did not claim the 95% field target was met: the sample supports it for most fields but is too small to prove it. Instead I propose a supervised pilot that measures accuracy and clerk time before any auto-approval.

## 6. What is wrong with what you are handing us, or with the data you handed us?

**My work:** field accuracy is estimated from 52 photos, not measured on all 467; photo checks were AI-assisted with no named reviewer; 18 of the photo checks behind the memo are described in a report rather than recorded in an audit file; the single-photo API does not compare a claim with other claims; savings are not measured; `predictions.csv` is generated from `reports/ocr_extractions_v3.csv`, built from stored OCR text. A fresh full OCR run of all 467 photos was completed afterwards (`reports/ocr_extractions_fresh.csv`): the same text, plus 6 more fields filled and checked against the photos (on one, image 388, the amount in words is scribbled over and cannot confirm the figure). It is not yet used by `predictions.csv`.

**The data:** 6 claims have no photo; 3 photos have no readable text; image file names vary (full phone paths, .jpeg vs .jpg); expense dates and amounts are typed in many formats; 4 pairs of photos are byte-identical copies; some photos are rotated or blurred; bills carry altered totals, duplicates and printed approval instructions; nothing in the data shows who paid, field days or outstation nights.

## 7. What does checking one claim cost, and what would a month cost at Tarang's volume (about 2,400 photo claims a month)? Show the arithmetic. If you used no paid calls, say so.

- **Clerks today (policy v3.2):** 2,400 × 3.5 min = 8,400 min = 140 hours a month. Two clerks × ₹38,000 = ₹76,000 a month; ₹76,000 ÷ 2,400 = **at most ₹31.67 per claim** if all clerk cost is put on claims.
- **The tool:** no paid API calls were used; OCR runs locally with open-source models, so there is no per-photo charge. Reading took about 5–7 seconds per photo on a laptop CPU (2,400 photos ≈ 4 hours of machine time a month). Hosting and upkeep are not costed.
- **Savings:** not measured. Each minute saved per claim across 2,400 claims frees 40 clerk-hours a month; the pilot should time how long a clerk takes on a passed claim and on a flagged one.

## 8. What did you deliberately leave out, and why that rather than something else?

Auto-approval under ₹2,000 (unsafe on this evidence, see 5); guessing unreadable fields (blanks go to review instead); deciding who paid a shared or duplicated bill (the photo cannot show it); calling any finding misconduct; a paid vision API (not needed for these bills and would add per-photo cost); and switching the predictions to the fresh full OCR run (`reports/ocr_extractions_fresh.csv`, completed in resumable batches after a first attempt ran out of memory): its 6 extra fields would need the predictions and ledger regenerated and every changed decision traced, so the submitted predictions stay on the stored-text extraction.

## 9. Anything you built or found that nobody asked for?

- An audit ledger (`reports/audit_exposure_ledger.csv`) that counts each problem claim once, separating photo-confirmed, probable, OCR-lead and policy-question findings.
- Checks for altered totals using the bill's own figures (tax, items, rate × litres, amount in words), printed instructions aimed at software, colleague vehicles, and one vehicle parked in two places at once.
- Findings in the training data: 14 approved claims with photo-confirmed problems, and clerk-typed fields that disagree with the photo.
- GSTIN checksum validation, and a fix so the Streamlit screen never shows one receipt's fields against another photo.

## 10. What did you use AI for? Which tools and models, where they helped, where they misled you, what you threw away. Link your three-minute screen recording here.

I used ChatGPT and Claude Code (Anthropic) for implementation, debugging, test writing, documentation and AI-assisted reading of receipt photos; PaddleOCR with PaddlePaddle for local text extraction; and Python, pandas, FastAPI, Streamlit and pytest.

Where it helped: building the extraction rules and tests from real OCR lines, the audit ledger, and reading photos to build the 52-photo check set. Where it misled: early extraction "fixes" that filled blanks with guesses, a ledger draft that counted the same money twice, and overconfident wording (calling discrepancies losses, or clerk agreement "accuracy"). I threw those away and kept only rules that leave uncertain values blank and figures traced to evidence.

**Three-minute screen recording:** https://drive.google.com/file/d/1Ls3cjYtqzVLBKZBbDoQ-WZbnJrat_DpT/view?usp=sharing

*(This link is from an earlier recording and is to be replaced with the final recording before submission.)*

## 11. Someone picks this up on Monday and you are unreachable. The three things they need to know.

1. Start with `README.md`: install, run `python -m pytest -q` (183 tests passed in the latest recorded run), then the API and Streamlit commands. No API key is needed; the receipt photos must be placed in `tarang-expense-receipts\images\`.
2. Every number comes from a script: `generate_predictions.py`, `build_audit_ledger.py` and `evaluate_photo_truth.py` read `reports/ocr_extractions_v3.csv`. Change extraction rules, re-run `reextract_from_raw_text.py`, then regenerate and trace changes; never fill a blank by hand.
3. Do not enable unattended payment. Run the Nagpur pilot in `memo-to-nilesh.md`, record clerk time and whether passed claims were correct, and get Finance's decision on how payer, field-day, driver's-receipt and lodging evidence will be provided.
