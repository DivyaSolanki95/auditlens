"""
AuditLens - Step 1: generate a synthetic procure-to-pay (P2P) ledger
with deliberately planted control failures, so every audit test can be
validated against known ground truth.

Tables: vendors, users, purchase_orders, invoices, payments
Ground truth: data/planted_anomalies.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
OUT = Path("data")
OUT.mkdir(exist_ok=True)

N_VENDORS = 400
N_USERS = 40
N_PO = 12000
APPROVAL_LIMIT = 100000  # INR; POs at or above this need manager approval
DEPTS = ["IT", "Facilities", "Marketing", "Operations", "Finance", "HR", "Logistics", "R&D"]
CITIES = ["Delhi", "Gurugram", "Noida", "Mumbai", "Pune", "Bengaluru", "Hyderabad", "Chennai"]

# ---------------- vendors ----------------
vendors = pd.DataFrame({
    "vendor_id": [f"V{i:04d}" for i in range(1, N_VENDORS + 1)],
    "vendor_name": [f"Vendor {i:04d} Pvt Ltd" for i in range(1, N_VENDORS + 1)],
    "city": RNG.choice(CITIES, N_VENDORS),
    "bank_account": [f"ACCT{RNG.integers(10**9, 10**10)}" for _ in range(N_VENDORS)],
    "address": [f"{RNG.integers(1, 999)} Industrial Area Phase {RNG.integers(1, 5)}" for _ in range(N_VENDORS)],
    "gstin_present": RNG.random(N_VENDORS) > 0.03,
})

# ---------------- users ----------------
users = pd.DataFrame({
    "user_id": [f"U{i:03d}" for i in range(1, N_USERS + 1)],
    "role": RNG.choice(["Requester", "Approver", "AP Clerk"], N_USERS, p=[0.5, 0.25, 0.25]),
})
requesters = users.loc[users.role == "Requester", "user_id"].to_numpy()
approvers = users.loc[users.role == "Approver", "user_id"].to_numpy()

# ---------------- purchase orders ----------------
start = pd.Timestamp("2025-04-01")
days = pd.to_timedelta(RNG.integers(0, 365, N_PO), unit="D")
po_dates = start + days
# shift natural weekend dates to the next Monday so planted weekend entries stand out
po_dates = pd.DatetimeIndex([d + pd.Timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d for d in po_dates])

# log-normal amounts spanning several orders of magnitude (Benford-friendly), not round
amounts = np.round(np.exp(RNG.normal(10.2, 1.3, N_PO)), 2)
amounts = np.clip(amounts, 500, 5_000_000)
amounts = np.where(amounts % 1000 == 0, amounts + 37.45, amounts)

pos = pd.DataFrame({
    "po_id": [f"PO{i:06d}" for i in range(1, N_PO + 1)],
    "vendor_id": RNG.choice(vendors.vendor_id, N_PO),
    "department": RNG.choice(DEPTS, N_PO),
    "po_date": po_dates,
    "po_amount": amounts,
    "created_by": RNG.choice(requesters, N_PO),
})
pos["approved_by"] = np.where(pos.po_amount >= APPROVAL_LIMIT, RNG.choice(approvers, N_PO), "AUTO")

# ---------------- invoices & payments ----------------
inv = pd.DataFrame({
    "invoice_id": [f"INV{i:07d}" for i in range(1, N_PO + 1)],
    "po_id": pos.po_id,
    "vendor_id": pos.vendor_id,
    "invoice_date": pos.po_date + pd.to_timedelta(RNG.integers(3, 25, N_PO), unit="D"),
    "invoice_amount": pos.po_amount,  # normally equals PO
})
pay = pd.DataFrame({
    "payment_id": [f"PAY{i:07d}" for i in range(1, N_PO + 1)],
    "invoice_id": inv.invoice_id,
    "vendor_id": inv.vendor_id,
    "payment_date": inv.invoice_date + pd.to_timedelta(RNG.integers(5, 40, N_PO), unit="D"),
    "amount": inv.invoice_amount,
    "posted_by": RNG.choice(users.loc[users.role == "AP Clerk", "user_id"], N_PO),
})
pay["payment_date"] = [d + pd.Timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d for d in pay.payment_date]

planted = []  # (test, record_id)

def pick(n, pool):
    return RNG.choice(pool, n, replace=False)

used = set()
def fresh(n):
    pool = [i for i in range(N_PO) if i not in used]
    idx = pick(n, pool)
    used.update(idx)
    return idx

# T1 duplicate payments: re-pay an existing invoice within 3 days
dup_src = fresh(40)
dups = pay.iloc[dup_src].copy()
dups["payment_id"] = [f"PAYD{i:05d}" for i in range(len(dups))]
dups["payment_date"] = dups.payment_date + pd.to_timedelta(RNG.integers(0, 4, len(dups)), unit="D")
pay = pd.concat([pay, dups], ignore_index=True)
planted += [("T1_duplicate_payment", p) for p in dups.payment_id]

# T2 split purchases: one requirement split into 2-3 POs just under the limit, same vendor, same week
split_rows = []
for k in range(25):
    v = RNG.choice(vendors.vendor_id); d = start + pd.Timedelta(days=int(RNG.integers(0, 350)))
    d = d + pd.Timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d
    req = RNG.choice(requesters); dept = RNG.choice(DEPTS)
    for j in range(int(RNG.integers(2, 4))):
        pid = f"POS{k:03d}{j}"
        split_rows.append({"po_id": pid, "vendor_id": v, "department": dept,
                           "po_date": d + pd.Timedelta(days=j), "po_amount": float(RNG.uniform(85000, 99900)).__round__(2),
                           "created_by": req, "approved_by": "AUTO"})
        planted.append(("T2_split_purchase", pid))
pos = pd.concat([pos, pd.DataFrame(split_rows)], ignore_index=True)

# T3 round-sum payments
idx = fresh(60)
pay.loc[idx, "amount"] = RNG.choice([25000, 50000, 75000, 100000, 200000, 500000], len(idx)).astype(float)
inv.loc[idx, "invoice_amount"] = pay.loc[idx, "amount"].values
pos.loc[idx, "po_amount"] = pay.loc[idx, "amount"].values
planted += [("T3_round_amount", p) for p in pay.loc[idx, "payment_id"]]

# T4 weekend postings
idx = fresh(50)
pay.loc[idx, "payment_date"] = [d + pd.Timedelta(days=(5 - d.weekday()) % 7 + int(RNG.integers(0, 2))) for d in pay.loc[idx, "payment_date"]]
planted += [("T4_weekend_posting", p) for p in pay.loc[idx, "payment_id"]]

# T5 payment before invoice date
idx = fresh(45)
pay.loc[idx, "payment_date"] = inv.loc[idx, "invoice_date"].values - pd.to_timedelta(RNG.integers(1, 10, len(idx)), unit="D")
pay.loc[idx, "payment_date"] = [d - pd.Timedelta(days=d.weekday() - 4) if d.weekday() >= 5 else d for d in pay.loc[idx, "payment_date"]]
planted += [("T5_paid_before_invoice", p) for p in pay.loc[idx, "payment_id"]]

# T6 invoice above PO (overbilling > 5%)
idx = fresh(55)
factor = RNG.uniform(1.08, 1.4, len(idx))
inv.loc[idx, "invoice_amount"] = np.round(inv.loc[idx, "invoice_amount"].values * factor, 2)
pay.loc[idx, "amount"] = inv.loc[idx, "invoice_amount"].values
planted += [("T6_invoice_over_po", i) for i in inv.loc[idx, "invoice_id"]]

# T7 vendors sharing a bank account (ghost / related vendors)
pairs = RNG.choice(vendors.index, (15, 2), replace=False)
for a, b in pairs:
    vendors.loc[b, "bank_account"] = vendors.loc[a, "bank_account"]
    planted += [("T7_shared_bank_account", vendors.loc[a, "vendor_id"]), ("T7_shared_bank_account", vendors.loc[b, "vendor_id"])]

# T8 segregation of duties: creator approves own PO (above limit)
big = pos.index[(pos.po_amount >= APPROVAL_LIMIT) & (~pos.index.isin(list(used)))]
idx = RNG.choice(big, 35, replace=False)
pos.loc[idx, "approved_by"] = pos.loc[idx, "created_by"].values
planted += [("T8_sod_conflict", p) for p in pos.loc[idx, "po_id"]]

# T9 Benford manipulation: Marketing payments fabricated just under the approval limit (first digits 4-9)
mkt_po = set(pos.loc[pos.department == "Marketing", "po_id"])
mkt_inv = inv.index[inv.po_id.isin(mkt_po) & ~inv.index.isin(list(used))]
idx = RNG.choice(mkt_inv, 400, replace=False)
used.update(idx)
fake = np.round(RNG.uniform(40000, 99000, len(idx)), 2)
pay.loc[idx, "amount"] = fake; inv.loc[idx, "invoice_amount"] = fake
fake_map = dict(zip(inv.loc[idx, "po_id"], fake))
pos["po_amount"] = pos.po_id.map(fake_map).fillna(pos.po_amount)
planted.append(("T9_benford_department", "Marketing"))

# T10 vendor spend spike: one month with a huge spike for a few vendors
spike_vendors = RNG.choice(vendors.vendor_id, 8, replace=False)
spike_rows = []
for v in spike_vendors:
    d = pd.Timestamp("2026-02-02") + pd.Timedelta(days=int(RNG.integers(0, 20)))
    d = d + pd.Timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d
    for j in range(6):
        pid = f"PAYS{v}{j}"
        spike_rows.append({"payment_id": pid, "invoice_id": None, "vendor_id": v,
                           "payment_date": d + pd.Timedelta(days=j % 4 if (d + pd.Timedelta(days=j % 4)).weekday() < 5 else 0),
                           "amount": float(RNG.uniform(600000, 1500000)).__round__(2), "posted_by": "U001"})
    planted.append(("T10_vendor_spike", v))
pay = pd.concat([pay, pd.DataFrame(spike_rows)], ignore_index=True)

# save
vendors.to_csv(OUT / "vendors.csv", index=False)
users.to_csv(OUT / "users.csv", index=False)
pos.to_csv(OUT / "purchase_orders.csv", index=False)
inv.to_csv(OUT / "invoices.csv", index=False)
pay.to_csv(OUT / "payments.csv", index=False)
pd.DataFrame(planted, columns=["test", "record_id"]).drop_duplicates().to_csv(OUT / "planted_anomalies.csv", index=False)

print(f"vendors={len(vendors)} users={len(users)} POs={len(pos)} invoices={len(inv)} payments={len(pay)}")
print(f"planted anomalies={len(set(planted))}")
