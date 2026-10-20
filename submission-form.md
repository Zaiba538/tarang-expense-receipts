# Tarang Pharma Distribution — Submission Form

## 1. GitHub repository URL

[PASTE YOUR PUBLIC GITHUB REPOSITORY URL HERE]

The repository should contain the application code, README, memo, reports, tests, and `predictions.csv` at the repository root.

## 2. What did you build, and what decision does it support for Nilesh? State the number and the rupees.

I built an OCR-assisted receipt review prototype that extracts receipt fields, validates available evidence, checks applicable policy rules and potential duplicates, and returns an approve or review recommendation.

The generated test file contains 190 claims. The current training evaluation covered 283 claims, matched 280 receipt images, and agreed with historical approve/review labels on 88 claims (31.1%). This is historical-label agreement, not verified policy accuracy.

At an illustrative loaded staff cost of ₹200/hour and 3 minutes of manual typing per claim, 2,400 claims require 120 hours/month, equivalent to ₹24,000 of typing time. If the tool saves 1 minute per claim, the time value is ₹8,000/month; if it saves 2 minutes, it is ₹16,000/month. These are scenarios, not measured savings. A pilot must measure actual time saved.

## 3. What do you expect predictions.csv to score on the hidden answers, field by field and on the approve/review decision, and why? Say how you estimated it.

I would not claim a verified hidden-set score from the current evidence. The current OCR run processed 467 receipt images. It left 3 vendor fields, 91 dates, 32 receipt numbers, 302 GSTINs, and 37 amounts blank. These are extraction completeness figures, not field accuracy scores.

My provisional expectation is that vendor and amount extraction will be stronger than GSTIN extraction, while dates and receipt numbers will be affected by image quality, receipt layouts, and OCR confusion. These expectations are qualitative, not measured accuracy percentages.

The training decision comparison showed 31.1% agreement with historical labels. I would not extrapolate this directly to the hidden set because historical statuses are imperfect reference labels and the training and test evidence may differ. A defensible numerical score estimate requires field-by-field comparison against manually verified training receipts and a separate decision evaluation.

## 4. How do you know it works? What did you measure it against, how did you get those answers, how many receipts, and what kinds of receipts does it get wrong?

The prototype was tested with automated unit and API tests; the recorded baseline was 56 passing tests. Receipt extraction processed 467 images, with 464 marked readable and 3 not marked readable. Six claims across the train and test datasets did not match a downloaded receipt image.

The training evaluation compared 283 predicted decisions with historical statuses and achieved 88/283 (31.1%) agreement. Historical clerk fields are useful reference data but are not independently verified ground truth. Field-level accuracy against manually verified receipt values has not yet been established.

Likely failure cases include blurry or low-contrast receipts, unusual layouts, ambiguous dates and receipt numbers, GSTINs that OCR cannot reliably distinguish, totals confused with subtotals, and policy requirements that cannot be inferred from the image alone. These require manual inspection and measurement rather than unsupported accuracy claims.

## 5. Did you change, narrow, or push back on Nilesh's ask? What, when, and why?

Yes. I would not automatically approve every claim under ₹2,000 based only on amount. Low-value claims can still be duplicates or fail policy requirements. The prototype routes claims to review when fields are missing, OCR is uncertain, amounts disagree, duplicate concerns arise, or required policy evidence is unavailable.

I recommend a shadow-mode pilot before enabling automatic payments. This preserves the goal of reducing clerical typing without treating a receipt photo or low claim value as proof of eligibility.

## 6. What is wrong with what you are handing us, or with the data you handed us?

The main limitations are:

- Training-label agreement is only 31.1%, and 195 historically approved claims were classified as review. The causes require investigation.
- Three training receipt images and three test receipt images were not matched to downloaded images.
- OCR output contains missing fields, especially GSTIN and receipt date.
- Some policy checks need evidence not represented in the structured claim data, such as field-day eligibility, outstation nights, driver receipts, and invoice type.
- Potential duplicate matches require human verification and must not be treated as proof of fraud.
- Field-level accuracy against independently checked receipts has not yet been measured.
- The clean-machine startup, UI, public repository, and recording must be verified before submission.

These limitations mean the prototype should not yet be used to authorize unattended reimbursement payments.

## 7. What does checking one claim cost, and what would a month cost at Tarang's volume? Show the arithmetic. If you used no paid calls, say so.

I have not yet measured the end-to-end cost of checking one claim in a live workflow, and I will not present a hypothetical labor estimate as a measured operating cost.

For an illustrative manual baseline of 3 minutes per claim and ₹200 per loaded staff hour:

- Manual typing time per claim: 3/60 = 0.05 hours.
- Illustrative labor value per claim: 0.05 × ₹200 = ₹10.
- Monthly manual typing time: 2,400 × 3/60 = 120 hours.
- Monthly labor value: 120 × ₹200 = ₹24,000.

If the prototype saves 1 minute per claim, it releases 40 hours/month, worth ₹8,000 at that assumed rate. If it saves 2 minutes per claim, it releases 80 hours/month, worth ₹16,000.

These are illustrative scenarios. Actual cost must include remaining clerk review time, hosting, maintenance, and any paid API usage. The implemented OCR pipeline uses local OCR; no paid model API calls were required for the recorded local runs. Any later API integration would need its own measured cost.

## 8. What did you deliberately leave out, and why that rather than something else?

I did not implement unconditional automatic approval for claims below ₹2,000 because amount alone does not establish policy compliance or rule out duplicate claims.

I also did not fabricate missing receipt fields or automatically reject claims with missing photos. The current focus is on extracting available evidence and routing uncertain cases to review. A production deployment would need a verified field-accuracy benchmark, stronger policy evidence, and a supervised pilot before expanding automatic approvals.

## 9. Anything you built or found that nobody asked for?

The prototype includes automated tests, image matching diagnostics, duplicate checks, claim-level training evaluation, and written error analysis. These additions help identify missing images and uncertain decisions rather than merely generating a CSV.

**Three-minute screen recording:** [PASTE YOUR SHAREABLE RECORDING LINK HERE]

## 10. What did you use AI for? Which tools and models, where they helped, where they misled you, what you threw away.

I used ChatGPT for implementation guidance, debugging, test development, documentation, and structuring the evaluation. I used PaddleOCR with PaddlePaddle for local receipt text extraction, along with Python, pandas, FastAPI, and pytest.

AI assistance helped troubleshoot implementation issues and organize the pipeline, but generated code and OCR results still required execution and verification. OCR sometimes missed or misread receipt fields, and the initial decision comparison showed that the rules were too conservative relative to historical statuses. I therefore documented these limitations instead of claiming unsupported accuracy.

No paid model API calls were required for the recorded local OCR and evaluation runs. The current prototype should be treated as an assisted-review system, not a fully validated autonomous reimbursement system.

## 11. Someone picks this up on Monday and you are unreachable. The three things they need to know.

1. Start with the root README and install the requirements in a Python virtual environment. Run `python -m pytest -q` and verify the current test results before making changes.
2. Regenerate OCR outputs and predictions only after confirming the receipt images and task CSV files are available. Check `predictions.csv` against `sample_submission.csv`; never invent missing fields.
3. Do not enable unattended automatic payments yet. Investigate the 31.1% historical-label agreement, measure field-level accuracy against verified receipts, and run a supervised shadow-mode pilot before changing decision thresholds.
