# AuditLens - Draft Audit Findings (procure-to-pay)

_Draft generated from the exception register. Every finding must be reviewed by a human auditor before sharing._

## Finding 1: Segregation-of-duties conflicts (High risk)

- **Condition:** 35 exception(s) identified; value INR 12,047,545.
- **Criteria:** The PO creator cannot approve the same PO (segregation of duties).
- **Cause (likely):** Approval workflow allows self-approval.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Remove self-approval rights; review all self-approved POs.

## Finding 2: Duplicate payments (High risk)

- **Condition:** 40 exception(s) identified; value INR 2,587,234.
- **Criteria:** Each invoice should be paid once.
- **Cause (likely):** No duplicate-invoice check before payment release.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Block payments matching vendor + invoice + amount; recover duplicates.

## Finding 3: Vendors sharing bank accounts (High risk)

- **Condition:** 30 exception(s) identified; value n/a.
- **Criteria:** Each vendor has a unique, verified bank account.
- **Cause (likely):** Weak vendor master-data controls.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Re-verify vendor bank details; investigate linked vendors for ghost-vendor risk.

## Finding 4: Invoices above purchase order (High risk)

- **Condition:** 55 exception(s) identified; value INR 6,053,776.
- **Criteria:** Invoice amount should not exceed PO by more than 5%.
- **Cause (likely):** Tolerance check missing or overridden.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Set a 5% tolerance block; recover overbilled amounts.

## Finding 5: Split purchases to avoid approval (High risk)

- **Condition:** 59 exception(s) identified; value INR 5,412,105.
- **Criteria:** POs at or above INR 1,00,000 require manager approval.
- **Cause (likely):** Requirements split into smaller POs to stay under the approval limit.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Aggregate same-vendor POs within 7 days for approval; review requesters involved.

## Finding 6: Payments before invoice date (High risk)

- **Condition:** 45 exception(s) identified; value INR 2,333,704.
- **Criteria:** Payment only after a valid invoice is received (3-way match).
- **Cause (likely):** 3-way match control bypassed.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Enforce PO-GRN-invoice match in the ERP before payment.

## Finding 7: Vendor spend spikes (Medium risk)

- **Condition:** 11 exception(s) identified; value INR 63,713,257.
- **Criteria:** Vendor spend should be consistent with contracts and history.
- **Cause (likely):** Unusual spend not reviewed by procurement.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Review contracts and deliveries for spike months; add spend-spike alerts.

## Finding 8: Benford's law nonconformity (Medium risk)

- **Condition:** 1 exception(s) identified; value n/a. Marketing shows MAD 0.0345 (Nonconformity) versus 'Close' for most departments.
- **Criteria:** Payment amounts in a large population usually follow Benford's law.
- **Cause (likely):** Possible fabricated amounts clustered below the approval limit.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Perform detailed testing of the department's payments between INR 40,000 and 99,999.

## Finding 9: Round-sum payments (Low risk)

- **Condition:** 60 exception(s) identified; value INR 9,075,000.
- **Criteria:** Invoices should reflect actual goods/services at exact amounts.
- **Cause (likely):** Possible estimates or unsupported invoices.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Request supporting documents for round-sum payments above INR 10,000.

## Finding 10: Weekend postings (Low risk)

- **Condition:** 58 exception(s) identified; value INR 4,260,135.
- **Criteria:** Payments are posted on business days under supervision.
- **Cause (likely):** Weak system restrictions on off-hours posting.
- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.
- **Recommendation:** Restrict weekend posting rights; require supervisor sign-off.

## Highest-risk vendors

- V0375: risk score 22, 6 exceptions across 5 tests
- V0138: risk score 19, 5 exceptions across 3 tests
- V0107: risk score 14, 3 exceptions across 3 tests
- V0278: risk score 14, 3 exceptions across 3 tests
- V0298: risk score 14, 3 exceptions across 3 tests