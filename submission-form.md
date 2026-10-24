# Tarang Pharma Distribution — Submission Form

## 1. GitHub repository URL

**GitHub URL:** https://github.com/Zaiba538/tarang-expense-receipts

The repository contains the application code, tests, README, `memo-to-nilesh.md`, evidence reports, audit files and `predictions.csv` at the repository root.

## 2. What did you build, and what decision does it support for Nilesh? State the number and the rupees.

A receipt-review tool (FastAPI service, Streamlit screen and batch pipeline) that reads vendor, bill date, bill number, GSTIN and total from the photo with local OCR, then checks each claim against its own bill (including altered totals and the amount in words), the expense policy, and other claims (duplicate bills, colleague vehicles, one vehicle in two car parks at once, printed "approve this" instructions).

The decision it supports: **do not auto-approve under ₹2,000 yet; run a four-week supervised pilot.** In the 190 new claims it found, with money counted once per claim or duplicate group: 8 claims exceeding what the bill supports (₹5,470.23 potential exposure, photo-confirmed); 6 items covering 7 claims that cannot be validly claimed (₹3,834.00, photo-confirmed; one item is a duplicate group of two claims); 2 probable (₹2,000.00); and 7 unchecked OCR leads (₹3,196.80). These are potential exposures on unpaid claims, not losses, recoverable money or savings.

Nilesh's rule (approve everything under ₹2,000) would approve 176 of the 190, including 34 claims with risk findings (18 of them unverified OCR leads) and ₹14,001.03 of potential exposure. The current checks approve 80 and send 110 to review. Today's checking costs 140 clerk-hours a month (2,400 × 3.5 min) and ₹76,000 a month for two clerks, at most ₹31.67 per claim; the tool has no per-photo charge. *Scenario, not measured:* if the 42% of claims that pass each save 1–3.5 clerk minutes, that frees about 17–59 hours, roughly ₹3,600–₹12,700 a month, assuming 176 working hours per clerk (₹215.9 an hour) and this batch's pass rate. Only a timed pilot can show the real saving.

## 3. What do you expect predictions.csv to score on the hidden answers, field by field and on the approve/review decision, and why? Say how you estimated it.

Estimated from 52 receipt photos I read by eye (`audit/photo_field_truth.csv`; 30 random within layout families, 22 deliberately difficult), plus the blanks in `predictions.csv`:

- **Vendor:** about 97–98%. 49/49 photo-checked; 4 of 190 are blank (3 claims have no photo, 1 photo has no readable text).
- **Receipt date:** about 94–97%. 46/46 photo-checked (the three dates the first OCR pass missed were read by the second pass; they are the misses that prompted the change, so they are not independent evidence); 5 of 190 blank.
- **Receipt number:** about 95–97%. 47/48 photo-checked; 5 of 190 blank.
- **GSTIN:** about 95–98%. 47/48 photo-checked, checksum-validated; blank is correct for bills without a GSTIN.
- **Total amount:** about 93–96%. 46/47 photo-checked; 8 of 190 blank. Where a bill's total was altered in ink, I report the figure as displayed: seven sample totals (images 019, 042, 050, 099, 166, 276, 457) are scored correct because they match the displayed figure, although the receipts are altered or contradict themselves. If the hidden answer uses the original printed figure, those will miss.

Every miss in the sample was a blank, never a wrong value, so the score is roughly the share of non-blank fields times a high read rate. The sample is small, so these are estimates, not measurements.

**Decision:** I expect lower agreement than on the fields. The tool sends 110 of 190 claims to review, many for policy evidence the data cannot show (fuel field day, driver's receipt, lodging conditions, payer), while on training claims Finance historically approved 275 of 283. On training claims my decisions agree with historical status on 127/283 (44.9%); historical approvals are not proof of compliance, and the ledger counts 14 photo-confirmed items covering 17 historically approved training claims.

## 4. How do you know it works? What did you measure it against, how did you get those answers, how many receipts, and what kinds of receipts does it get wrong?

- **Photos read by eye:** 52 receipts across 9 layouts (cab, courier, fuel, handwritten, hotel, no-text, parking, restaurant, other). Results in `reports/photo_field_evaluation.md`. A further 47 photo findings are recorded in `audit/photo_review_findings.csv`.
- **Targeted photo checks:** 67 checks on 46 images, recorded in `audit/photo_checks_followup.csv` (65 confirmed, 1 probable, 1 uncertain). The images were chosen for a reason (new approvals, changed values, conflicts), so they are not a representative sample and do not feed any accuracy figure.
- **Clerk entries** on 283 training claims, as agreement only, not accuracy (clerks are sometimes wrong: in the photo sample, clerk vendor was wrong on 5 of 33 bills).
- **208 automated tests** passed when the full suite was re-run on 25 October 2026, including regression tests built from real OCR lines.

It gets wrong, by leaving blank: blurred or black photos (3 have no text), handwritten or blurred dates the OCR misses, totals whose handwritten "/-" OCR misreads when the amount in words is also unreadable, and a total label covered by a pen note. A second, enhanced OCR pass recovers some of these (7 fields on 6 test claims (5 in the submitted prediction columns)); a claim that relies on such a value goes to review for a clerk to confirm it. OCR also varies when the same photo is re-compressed, and on one blurred bill (image 459) both passes misread the subtotal, so a correct ₹1,082 total carries a false "not supported" warning. A missing date, bill number or total sends a test claim to review; a missing GSTIN alone does not always (image 122's blank GSTIN is on an approved courier claim).

## 5. Did you change, narrow, or push back on Nilesh's ask? What, when, and why?

Yes. Nilesh asked for auto-approval of everything under ₹2,000. After reading the photos I recommended against switching it on now: in this batch, claims under ₹2,000 include totals altered in ink, the same bill claimed twice (sometimes by two employees), fuel for a colleague's vehicle, and bills printed with instructions telling software to approve and skip duplicate checks. A ₹2,000 threshold alone would pay all of these. I also did not claim the 95% field target was met: in the 52-photo sample every field now reaches at least 95% (dates 46/46 after the second OCR pass), but 22 of those photos were chosen as difficult, the three recovered dates are the misses that prompted the change, and the sample is too small to prove the target for any field across the dataset. Instead I propose a supervised pilot that measures accuracy and clerk time before any auto-approval.

## 6. What is wrong with what you are handing us, or with the data you handed us?

**My work:** field accuracy is estimated from 52 photos, not measured on all 467; photo checks were AI-assisted by a single reviewer with no named person, so they are not independent; one plate (image 063) is uncertain: it reads `MH34BT9842` while the claimant's registered plate is `MH34 BT 9042`; the single-photo API does not compare a claim with other claims; the live `/review` endpoint has been tested with real OCR on one photo only, the Streamlit upload-to-decision flow has not been tested in a browser, and installation has not been tested on a clean machine; the Streamlit screen does not pass on which values came from the second OCR pass, so it does not apply the second-pass review rule (the clerk confirms each field there); savings are not measured; the linked screen recording's duration and whether it shows the current version have not been verified. `predictions.csv` is generated from `reports/ocr_extractions_v4.csv`: the fresh full OCR run of all 467 photos, re-extracted with the current rules. Its second pass recovered 7 fields across 6 test claims (5 of them in the submitted prediction columns) that match the photos (on one, image 388, the amount in words is scribbled over, so the ₹1,100 total is probable, not confirmed); those claims stay in review. Image 459 keeps a false arithmetic warning (see 4).

**The data:** 6 claims have no photo; 3 photos have no readable text; image file names vary (full phone paths, .jpeg vs .jpg); expense dates and amounts are typed in many formats; 4 pairs of photos are byte-identical copies; some photos are rotated or blurred; bills carry altered totals, duplicates and printed approval instructions; nothing in the data shows who paid, field days or outstation nights.

## 7. What does checking one claim cost, and what would a month cost at Tarang's volume (about 2,400 photo claims a month)? Show the arithmetic. If you used no paid calls, say so.

- **Clerks today (policy v3.2):** 2,400 × 3.5 min = 8,400 min = 140 hours a month. Two clerks × ₹38,000 = ₹76,000 a month; ₹76,000 ÷ 2,400 = **at most ₹31.67 per claim** if all clerk cost is put on claims.
- **The tool:** no paid API calls were used; OCR runs locally with open-source models, so there is no per-photo charge. On a laptop CPU the first OCR pass took about 5–7 seconds per photo; the fresh resumable run, including the enhanced second pass where needed, averaged about 10–11 seconds. Estimate: approximately 3.3–7.3 machine-hours for 2,400 photos a month (2,400 × 5 s = 12,000 s ≈ 3.3 h; 2,400 × 11 s = 26,400 s ≈ 7.3 h). Hosting and upkeep are not costed.
- **Savings:** not measured. Each minute saved per claim across 2,400 claims frees 40 clerk-hours a month. *Scenario, not measured:* if the 42% of claims that pass (about 1,011 a month) each save 1–3.5 minutes, that is about 17–59 hours, roughly ₹3,600–₹12,700 a month, assuming 176 working hours per clerk (₹76,000 ÷ 352 h = ₹215.9 an hour) and this batch's pass rate. The pilot should time how long a clerk takes on a passed claim and on a flagged one.

## 8. What did you deliberately leave out, and why that rather than something else?

Auto-approval under ₹2,000 (unsafe on this evidence, see 5); guessing unreadable fields (blanks go to review instead); deciding who paid a shared or duplicated bill (the photo cannot show it); calling any finding misconduct; cross-claim checks (duplicates, colleague vehicles, parking overlaps) in the single-photo API, which run only in the batch pipeline; a paid vision API (not needed for these bills and would add per-photo cost); approving a claim on a value only the second OCR pass could read (it goes to a clerk instead, so the 7 fields recovered across 6 test claims changed no decision); and repairing OCR misreads of a bill's figures, such as image 459's subtotal, by guesswork (the claim stays in review).

## 9. Anything you built or found that nobody asked for?

- An audit ledger (`reports/audit_exposure_ledger.csv`) that counts each problem claim once, separating photo-confirmed, probable, OCR-lead and policy-question findings.
- Checks for altered totals using the bill's own figures (tax, items, rate × litres, amount in words), printed instructions aimed at software, colleague vehicles, and one vehicle parked in two places at once.
- Findings in the training data: 14 photo-confirmed items covering 17 historically approved claims, and clerk-typed fields that disagree with the photo.
- A follow-up audit file (`audit/photo_checks_followup.csv`) recording 67 targeted photo checks with their source and confidence.
- A dataset-wide extraction audit: 17 vehicle plates recovered from the fresh OCR text (all in `reports/ocr_extractions_v4.csv`, which predictions use; one, image 063, is uncertain) and 2 wrong totals left blank instead (a Km reading and an item price); each change was compared with its photo.
- A resumable, checkpointed OCR run, so a long run can continue after an interruption; the predictions now use it, re-extracted with the current rules; and a check for one vehicle parked in two car parks at overlapping times (two pairs found, one in the test batch).
- GSTIN checksum validation, and a fix so the Streamlit screen never shows one receipt's fields against another photo.

## 10. What did you use AI for? Which tools and models, where they helped, where they misled you, what you threw away. Link your three-minute screen recording here.

I used ChatGPT and Claude Code (Anthropic) for implementation, debugging, test writing, documentation and AI-assisted reading of receipt photos; PaddleOCR with PaddlePaddle for local text extraction; and Python, pandas, FastAPI, Streamlit and pytest.

Where it helped: building the extraction rules and tests from real OCR lines, the audit ledger, and reading photos to build the 52-photo check set. Where it misled: early extraction "fixes" that filled blanks with guesses, a ledger draft that counted the same money twice, and overconfident wording (calling discrepancies losses, or clerk agreement "accuracy"). I threw those away and kept only rules that leave uncertain values blank and figures traced to evidence.

**Three-minute screen recording:** https://drive.google.com/file/d/1Ls3cjYtqzVLBKZBbDoQ-WZbnJrat_DpT/view?usp=sharing

*(This link is from an earlier recording and is to be replaced with the final recording before submission.)*

## 11. Someone picks this up on Monday and you are unreachable. The three things they need to know.

1. Start with `README.md`: install, run `python -m pytest -q` (208 tests passed when re-run on 25 October 2026), then the API and Streamlit commands. No API key is needed; the receipt photos must be placed in `tarang-expense-receipts\images\`.
2. Every number comes from a script: `generate_predictions.py`, `build_audit_ledger.py` and `evaluate_photo_truth.py` read `reports/ocr_extractions_v4.csv`. Change extraction rules, re-run `reextract_from_raw_text.py` on `reports/ocr_extractions_fresh.csv` (never use that raw file directly; the scripts refuse it), then regenerate and trace changes; never fill a blank by hand.
3. Do not enable unattended payment. Run the Nagpur pilot in `memo-to-nilesh.md`, record clerk time and whether passed claims were correct, and get Finance's decision on how payer, field-day, driver's-receipt and lodging evidence will be provided.
