"""
AuditLens - Step 3: draft audit findings in internal audit's 5C format
(Condition, Criteria, Cause, Effect, Recommendation).

Default: rule-based draft from the exception register (no API needed).
Optional: set OPENAI_API_KEY to have an LLM polish the wording.
A human reviewer must check every finding before it is shared.
"""
import os
import pandas as pd
from pathlib import Path

OUT = Path("output")
XL = OUT / "AuditLens_Exception_Register.xlsx"
reg = pd.read_excel(XL, sheet_name="Exception_Register")
vrisk = pd.read_excel(XL, sheet_name="Vendor_Risk")
benf = pd.read_excel(XL, sheet_name="Benford_by_Dept")

CRITERIA = {
    "T1_duplicate_payment": ("Each invoice should be paid once.", "No duplicate-invoice check before payment release.", "Block payments matching vendor + invoice + amount; recover duplicates."),
    "T2_split_purchase": ("POs at or above INR 1,00,000 require manager approval.", "Requirements split into smaller POs to stay under the approval limit.", "Aggregate same-vendor POs within 7 days for approval; review requesters involved."),
    "T3_round_amount": ("Invoices should reflect actual goods/services at exact amounts.", "Possible estimates or unsupported invoices.", "Request supporting documents for round-sum payments above INR 10,000."),
    "T4_weekend_posting": ("Payments are posted on business days under supervision.", "Weak system restrictions on off-hours posting.", "Restrict weekend posting rights; require supervisor sign-off."),
    "T5_paid_before_invoice": ("Payment only after a valid invoice is received (3-way match).", "3-way match control bypassed.", "Enforce PO-GRN-invoice match in the ERP before payment."),
    "T6_invoice_over_po": ("Invoice amount should not exceed PO by more than 5%.", "Tolerance check missing or overridden.", "Set a 5% tolerance block; recover overbilled amounts."),
    "T7_shared_bank_account": ("Each vendor has a unique, verified bank account.", "Weak vendor master-data controls.", "Re-verify vendor bank details; investigate linked vendors for ghost-vendor risk."),
    "T8_sod_conflict": ("The PO creator cannot approve the same PO (segregation of duties).", "Approval workflow allows self-approval.", "Remove self-approval rights; review all self-approved POs."),
    "T9_benford_department": ("Payment amounts in a large population usually follow Benford's law.", "Possible fabricated amounts clustered below the approval limit.", "Perform detailed testing of the department's payments between INR 40,000 and 99,999."),
    "T10_vendor_spike": ("Vendor spend should be consistent with contracts and history.", "Unusual spend not reviewed by procurement.", "Review contracts and deliveries for spike months; add spend-spike alerts."),
}

TITLES = {"T1_duplicate_payment": "Duplicate payments", "T2_split_purchase": "Split purchases to avoid approval", "T3_round_amount": "Round-sum payments", "T4_weekend_posting": "Weekend postings", "T5_paid_before_invoice": "Payments before invoice date", "T6_invoice_over_po": "Invoices above purchase order", "T7_shared_bank_account": "Vendors sharing bank accounts", "T8_sod_conflict": "Segregation-of-duties conflicts", "T9_benford_department": "Benford's law nonconformity", "T10_vendor_spike": "Vendor spend spikes"}
lines = ["# AuditLens - Draft Audit Findings (procure-to-pay)", "",
         "_Draft generated from the exception register. Every finding must be reviewed by a human auditor before sharing._", ""]
summary = reg.groupby("test").agg(count=("record_id", "count"), value=("amount_inr", "sum"), sev=("severity", "max"))
summary = summary.sort_values(["sev", "value"], ascending=False)
for i, (test, row) in enumerate(summary.iterrows(), 1):
    crit, cause, rec = CRITERIA[test]
    val = f"INR {row.value:,.0f}" if row.value > 0 else "n/a"
    rating = {5: "High", 4: "High", 3: "Medium", 2: "Low"}[int(row.sev)]
    extra = ""
    if test == "T9_benford_department":
        d = benf.sort_values("MAD", ascending=False).iloc[0]
        extra = f" {d.department} shows MAD {d.MAD} ({d.conformity}) versus 'Close' for most departments."
    lines += [f"## Finding {i}: {TITLES[test]} ({rating} risk)", "",
              f"- **Condition:** {int(row['count'])} exception(s) identified; value {val}.{extra}",
              f"- **Criteria:** {crit}", f"- **Cause (likely):** {cause}",
              f"- **Effect:** Financial loss, misstatement or fraud risk; weaker control environment.",
              f"- **Recommendation:** {rec}", ""]
top = vrisk.head(5)
lines += ["## Highest-risk vendors", ""] + [f"- {r.vendor_id}: risk score {r.risk_score}, {r.exceptions} exceptions across {r.distinct_tests} tests" for r in top.itertuples()]
memo = "\n".join(lines)

if os.getenv("OPENAI_API_KEY"):
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), messages=[
        {"role": "system", "content": "You are an internal audit senior. Polish these findings for a client report. Keep every number exactly as given; do not invent facts."},
        {"role": "user", "content": memo}])
    memo = resp.choices[0].message.content

(OUT / "AuditLens_Audit_Memo.md").write_text(memo)
print(memo[:1500])
