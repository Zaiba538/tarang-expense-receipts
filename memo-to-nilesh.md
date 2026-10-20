# Memo to Nilesh — Tarang Pharma Expense Receipt Review

**Subject:** Automating receipt entry while protecting reimbursement controls

## Recommendation

Pilot an OCR-assisted expense review workflow rather than automatically approving every claim under ₹2,000. The service extracts vendor, receipt date, receipt number, GSTIN and total amount, then applies available validation and policy checks. Claims with missing fields, uncertain OCR, amount mismatches or unresolved policy conditions are routed to a clerk.

The amount alone is not sufficient evidence that a claim is legitimate. A low-value claim can still contain a duplicate bill or fail a policy requirement. Missing or unreadable photos should trigger clarification, not an automatic rejection.

## What has been built

The prototype includes receipt OCR, field normalization, claim and receipt validation, rule-based decisions, duplicate checks, a FastAPI endpoint, automated tests and a CSV prediction pipeline. The generated test submission contains 190 claims.

The training evaluation covered 283 claims and matched 280 receipt images. The current system agreed with historical approve/review reference labels on 88 of 283 claims (31.1%). This is not verified policy accuracy: historical statuses are imperfect reference labels, and the high number of review decisions requires further investigation before deployment.

## Indicative monthly workload and cost

Tarang processes approximately 2,400 photo claims per month. Actual time savings have not yet been measured in a live clerk workflow, so the following figures are scenarios, not promised savings.

**Illustrative assumptions:** manual typing takes 3 minutes per claim, and loaded staff time costs ₹200 per hour.

- Current typing workload: 2,400 × 3 ÷ 60 = **120 hours/month**.
- Illustrative typing labor value: 120 × ₹200 = **₹24,000/month**.
- If the tool saves 1 minute of typing per claim on average: 2,400 × 1 ÷ 60 = **40 hours/month**, or **₹8,000/month** of time value.
- If it saves 2 minutes per claim: 2,400 × 2 ÷ 60 = **80 hours/month**, or **₹16,000/month** of time value.

These figures exclude review time, implementation and maintenance, infrastructure, any paid API calls, and any recoveries from duplicate or non-compliant claims. They represent potential capacity released, not necessarily cash savings or reduced headcount.

## What I need from Tarang

1. Clerks to verify a representative sample of OCR fields against original receipts.
2. Confirmation of policy interpretations and the evidence required for fuel, lodging and local travel.
3. Actual average typing and review times, plus the loaded hourly staff cost.
4. A supervised pilot with review outcomes recorded so field accuracy, decision quality and time saved can be measured.
5. Agreement on an acceptable false-approval risk before enabling any automatic payment.

## Proposed next step

Run the prototype in shadow mode: extract and recommend decisions without paying claims automatically. Measure field-level accuracy against independently checked receipts, record the reasons for review, and compare clerk handling time before and after the tool. Enable limited automatic approvals only after the evidence supports a safe threshold and duplicate and policy controls have been validated.

**Conclusion:** The prototype can reduce repetitive data entry, but the current evaluation does not justify automatic approval based solely on a ₹2,000 threshold. A measured pilot is the responsible route to quantify savings and build confidence.
