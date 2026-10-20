# What 2025 can say about today's lending: whose loans 2025's
# charge-offs were, and the early reads of the newest cohorts beside
# the push's, with the risk Mark II-R saw in each at the door.
import json

import numpy as np
import pandas as pd

import fernhill
from _chargeoffs import account_months, unemployment
from ballast import monitoring as mon
from ballast.config import ROOT
from ballast.parameters import pd as pdm

con = fernhill.connect()
m = account_months(con)
co = m[(m["month"].dt.year == 2025) & (m["off_cents"] > 0)]
by = co.groupby(pd.to_datetime(co["open_date"]).dt.year)["off_cents"]
share = by.sum() / co["off_cents"].sum()
print("2025's charge-offs by the year the loan was opened")
early = share[share.index < 2022].sum()
print("  " + "  ".join(f"{y}: {share[y]:.1%}" for y in
                       (2025, 2024, 2023, 2022))
      + f"  before: {early:.1%}")

reads = mon.early_reads(con, "personal", freq="H").set_index("vintage")
loans = pdm.personal_loans(con)
loans["promise"] = pdm.load_calibration().pd(loans["score"])
half = np.where(loans["open_month"].dt.month <= 6, "H1", "H2")
loans["vintage"] = loans["open_month"].dt.year.astype(str) + half
promise = loans.groupby("vintage")["promise"].mean()
u = unemployment(con, 0)

rows = []
print(f"\n{'opened':<8}{'loans':>6}{'promise':>9}{'60+ by month 6':>20}"
      f"{'90+ by 12':>11}{'jobless':>9}")
for v in [f"{y}{h}" for y in range(2021, 2026) for h in ("H1", "H2")]:
    r = reads.loc[v]
    start = pd.Timestamp(int(v[:4]), 1 if v[4:] == "H1" else 7, 1)
    jobless = u[start + pd.offsets.MonthEnd(1):
               start + pd.offsets.MonthEnd(6)].mean()
    if np.isnan(r.e6_60):
        e6 = f"{'.':>20}"
    else:
        k = round(r.e6_60 * r.loans)
        lo, hi = mon.binomial_interval(k, int(r.loans))
        e6 = f"{r.e6_60:>7.2%} ({lo:.1%} to {hi:.1%})"
        rows.append({"vintage": v, "e6_60": r.e6_60, "lo": lo, "hi": hi,
                     "promise": promise[v]})
    b12 = f"{r.b12:>11.2%}" if not np.isnan(r.b12) else f"{'.':>11}"
    print(f"{v:<8}{int(r.loans):>6,}{promise[v]:>9.2%}{e6:>20}{b12}"
          f"{jobless:>8.1f}%")
print("promise: Mark II-R's first-year PD at the door (Chapter 18);")
print("jobless: unemployment over the cohort's first six months")
print("the push: February 2021 to June 2022; intervals 95%")

(ROOT / "code/31/07_early_reads.json").write_text(
    json.dumps(rows) + "\n")
