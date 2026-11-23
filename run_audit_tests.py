"""
AuditLens - Step 2: run 10 procure-to-pay audit tests, score risk,
validate against planted ground truth, and export an exception register.
"""
import numpy as np
import pandas as pd
from pathlib import Path

D = Path("data"); OUT = Path("output"); OUT.mkdir(exist_ok=True)
APPROVAL_LIMIT = 100000

vendors = pd.read_csv(D / "vendors.csv")
pos = pd.read_csv(D / "purchase_orders.csv", parse_dates=["po_date"])
inv = pd.read_csv(D / "invoices.csv", parse_dates=["invoice_date"])
pay = pd.read_csv(D / "payments.csv", parse_dates=["payment_date"])
truth = pd.read_csv(D / "planted_anomalies.csv")

# ---- data-quality profile ----
dq = []
for name, df in {"vendors": vendors, "purchase_orders": pos, "invoices": inv, "payments": pay}.items():
    dq.append({"table": name, "rows": len(df), "null_cells": int(df.isna().sum().sum()),
               "duplicate_rows": int(df.duplicated().sum())})
dq = pd.DataFrame(dq)

ex = []  # exception register rows
def add(test, rec, amount, detail, weight):
    for r, a, d in zip(rec, amount, detail):
        ex.append({"test": test, "record_id": r, "amount_inr": a, "detail": d, "severity": weight})

# T1 duplicate payments: same vendor + amount + invoice, within 3 days
p = pay.dropna(subset=["invoice_id"]).sort_values(["payment_date", "payment_id"])
g = p.groupby(["vendor_id", "invoice_id", "amount"])
cand = p[g.payment_id.transform("count") > 1].copy()
cand["first_date"] = cand.groupby(["vendor_id", "invoice_id", "amount"]).payment_date.transform("min")
cand["rank"] = cand.groupby(["vendor_id", "invoice_id", "amount"]).payment_date.rank(method="first")
t1 = cand[(cand["rank"] > 1) & ((cand.payment_date - cand.first_date).dt.days <= 3)]
add("T1_duplicate_payment", t1.payment_id, t1.amount, ["Same invoice paid twice within 3 days"] * len(t1), 5)

# T2 split purchases: same vendor + requester, >=2 POs below limit within 7 days that together exceed it
s = pos[(pos.po_amount < APPROVAL_LIMIT) & (pos.po_amount >= 0.8 * APPROVAL_LIMIT)].sort_values("po_date")
flag = set()
for (v, c), grp in s.groupby(["vendor_id", "created_by"]):
    dates = grp.po_date.values; amts = grp.po_amount.values; ids = grp.po_id.values
    for i in range(len(grp)):
        win = (dates >= dates[i]) & (dates <= dates[i] + np.timedelta64(7, "D"))
        if win.sum() >= 2 and amts[win].sum() >= APPROVAL_LIMIT:
            flag.update(ids[win])
t2 = pos[pos.po_id.isin(flag)]
add("T2_split_purchase", t2.po_id, t2.po_amount, ["POs just under approval limit split within 7 days"] * len(t2), 4)

# T3 round-sum payments (multiple of 5,000 with no paise)
t3 = pay[(pay.amount % 5000 == 0) & (pay.amount >= 10000)]
add("T3_round_amount", t3.payment_id, t3.amount, ["Exact round amount"] * len(t3), 2)

# T4 weekend postings
t4 = pay[pay.payment_date.dt.day_of_week >= 5]
add("T4_weekend_posting", t4.payment_id, t4.amount, ["Posted on " + d.day_name() for d in t4.payment_date], 2)

# T5 payment before invoice date
m = pay.merge(inv[["invoice_id", "invoice_date"]], on="invoice_id", how="inner")
t5 = m[m.payment_date < m.invoice_date]
add("T5_paid_before_invoice", t5.payment_id, t5.amount,
    [f"Paid {(i - p).days} day(s) before invoice" for p, i in zip(t5.payment_date, t5.invoice_date)], 4)

# T6 invoice above PO by more than 5%
m = inv.merge(pos[["po_id", "po_amount"]], on="po_id")
t6 = m[m.invoice_amount > 1.05 * m.po_amount]
add("T6_invoice_over_po", t6.invoice_id, t6.invoice_amount,
    [f"Invoice {x / y - 1:.0%} above PO" for x, y in zip(t6.invoice_amount, t6.po_amount)], 4)

# T7 vendors sharing a bank account
shared = vendors[vendors.duplicated("bank_account", keep=False)]
add("T7_shared_bank_account", shared.vendor_id, [np.nan] * len(shared),
    ["Bank account shared with another vendor"] * len(shared), 5)

# T8 segregation of duties: creator approved own PO
t8 = pos[pos.created_by == pos.approved_by]
add("T8_sod_conflict", t8.po_id, t8.po_amount, ["Creator approved own PO"] * len(t8), 5)

# T9 Benford's law first-digit test by department (on payment amounts)
pm = pay.merge(inv[["invoice_id", "po_id"]], on="invoice_id", how="left").merge(pos[["po_id", "department"]], on="po_id", how="left")
pm["first_digit"] = pm.amount.astype(int).astype(str).str[0].astype(int)
benford = pd.Series({d: np.log10(1 + 1 / d) for d in range(1, 10)})
benf_rows = []
for dept, grp in pm.dropna(subset=["department"]).groupby("department"):
    obs = grp.first_digit.value_counts(normalize=True).reindex(range(1, 10), fill_value=0)
    mad = float((obs - benford).abs().mean())
    benf_rows.append({"department": dept, "n": len(grp), "MAD": round(mad, 4),
                      "conformity": "Close" if mad < 0.006 else "Acceptable" if mad < 0.012 else "Marginal" if mad < 0.015 else "Nonconformity"})
benf = pd.DataFrame(benf_rows)
t9 = benf[benf.conformity.isin(["Marginal", "Nonconformity"])]
add("T9_benford_department", t9.department, [np.nan] * len(t9), [f"Benford MAD {m} ({c}) on {n} payments" for m, c, n in zip(t9.MAD, t9.conformity, t9.n)], 3)
overall_obs = pm.first_digit.value_counts(normalize=True).reindex(range(1, 10), fill_value=0)

# T10 vendor spend spike: monthly vendor spend z-score > 3 vs that vendor's own history
pay["month"] = pay.payment_date.dt.to_period("M")
mv = pay.groupby(["vendor_id", "month"]).amount.sum().reset_index()
stats = mv.groupby("vendor_id").amount.agg(["median"])
mv = mv.merge(stats, on="vendor_id")
mad_v = mv.groupby("vendor_id").apply(lambda g: (g.amount - g["median"]).abs().median(), include_groups=False).rename("mad")
mv = mv.merge(mad_v, on="vendor_id")
mv["robust_z"] = 0.6745 * (mv.amount - mv["median"]) / mv["mad"].replace(0, np.nan)
t10 = mv[(mv.robust_z > 10) & (mv.amount > 5 * mv["median"]) & (mv.amount > 2_000_000)]
add("T10_vendor_spike", t10.vendor_id, t10.amount, [f"{m} spend {z:.1f} robust-z above normal" for m, z in zip(t10.month.astype(str), t10.robust_z)], 3)

reg = pd.DataFrame(ex)

# ---- validation against planted ground truth ----
val = []
for test, grp in truth.groupby("test"):
    flagged = set(reg.loc[reg.test == test, "record_id"])
    planted_ids = set(grp.record_id)
    tp = len(flagged & planted_ids)
    val.append({"test": test, "planted": len(planted_ids), "flagged": len(flagged), "caught": tp,
                "recall": round(tp / len(planted_ids), 3), "precision": round(tp / len(flagged), 3) if flagged else 0})
val = pd.DataFrame(val)

# ---- vendor risk score ----
rec_vendor = pd.concat([
    reg.merge(pay[["payment_id", "vendor_id"]], left_on="record_id", right_on="payment_id")[["test", "vendor_id", "severity"]],
    reg.merge(pos[["po_id", "vendor_id"]], left_on="record_id", right_on="po_id")[["test", "vendor_id", "severity"]],
    reg.merge(inv[["invoice_id", "vendor_id"]], left_on="record_id", right_on="invoice_id")[["test", "vendor_id", "severity"]],
    reg[reg.test.isin(["T7_shared_bank_account", "T10_vendor_spike"])].rename(columns={"record_id": "vendor_id"})[["test", "vendor_id", "severity"]],
])
vrisk = (rec_vendor.groupby("vendor_id")
         .agg(risk_score=("severity", "sum"), exceptions=("test", "count"), distinct_tests=("test", "nunique"))
         .sort_values(["risk_score", "distinct_tests"], ascending=False).reset_index())
vrisk["risk_band"] = pd.cut(vrisk.risk_score, [0, 4, 9, 1e9], labels=["Low", "Medium", "High"])

# ---- export ----
total_txn = len(pay) + len(pos) + len(inv)
summary = pd.DataFrame({
    "metric": ["Records tested (POs + invoices + payments)", "Vendors", "Exceptions flagged", "Planted anomalies",
               "Planted anomalies caught", "Overall recall", "Overall precision", "Value of flagged payments (INR)",
               "High-risk vendors"],
    "value": [total_txn, len(vendors), len(reg), int(val.planted.sum()), int(val.caught.sum()),
              round(val.caught.sum() / val.planted.sum(), 3), round(val.caught.sum() / val.flagged.sum(), 3),
              round(reg.loc[reg.record_id.astype(str).str.startswith("PAY"), "amount_inr"].sum(), 2),
              int((vrisk.risk_band == "High").sum())]})

with pd.ExcelWriter(OUT / "AuditLens_Exception_Register.xlsx") as xw:
    summary.to_excel(xw, sheet_name="Summary", index=False)
    val.to_excel(xw, sheet_name="Test_Validation", index=False)
    reg.sort_values(["severity", "amount_inr"], ascending=False).to_excel(xw, sheet_name="Exception_Register", index=False)
    vrisk.to_excel(xw, sheet_name="Vendor_Risk", index=False)
    benf.to_excel(xw, sheet_name="Benford_by_Dept", index=False)
    dq.to_excel(xw, sheet_name="Data_Quality", index=False)

# charts for README / dashboard mock
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(7, 4))
x = np.arange(1, 10)
ax.bar(x, overall_obs.values, color="#4C78A8", label="Observed")
ax.plot(x, benford.values, "o-", color="#E45756", label="Benford expected")
ax.set_xticks(x); ax.set_xlabel("First digit"); ax.set_ylabel("Share of payments")
ax.set_title("Payment amounts vs Benford's law"); ax.legend(); fig.tight_layout()
fig.savefig(OUT / "benford.png", dpi=150)

fig, ax = plt.subplots(figsize=(7, 4))
v = val.set_index("test")
ax.barh(v.index, v.recall, color="#4C78A8"); ax.set_xlim(0, 1.05)
ax.set_xlabel("Recall (share of planted anomalies caught)"); ax.set_title("Audit test validation")
fig.tight_layout(); fig.savefig(OUT / "test_validation.png", dpi=150)

pd.set_option("display.width", 200)
print(summary.to_string(index=False)); print(); print(val.to_string(index=False)); print(); print(benf.to_string(index=False))
print(); print(vrisk.head(10).to_string(index=False))
