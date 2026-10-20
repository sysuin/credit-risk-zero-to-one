# The growth push as a loosening of standards: the loans only the push
# made, against those the normal policy would have made anyway.
import pandas as pd

import fernhill
from ballast import data
from ballast import performance as perf
from ballast.decision import policy as pol
from ballast.decision import strategy

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")
        & raw["outcome"].astype(str).eq("booked")].copy()
p["day"] = pd.to_datetime(p["app_date"].astype("datetime64[s]"))
p = p[p["day"].between("2019-01-01", "2023-12-31")]
p["dti"] = pol.dti_at_decision(p)
eco = strategy.loan_economics(con, "personal")
acc = perf.cohort_accounts(con, "personal",
                           perf.default_episodes(con, "dod2021"))
p = (p.merge(eco[["account_id", "amount_cents", "profit"]],
             on="account_id")
      .merge(acc[["account_id", "default_mob"]], on="account_id"))
push = p["day"].between("2021-02-01", "2022-06-30")
# The normal policy: approve at 590 and up (580 plus the refer band)
# with a DTI of 0.50 or less.
normal = (p["mark1_score"] >= 590) & (p["dti"] <= 0.50)
rows = [("before the push: 575", p[p["day"] < "2020-04-01"]),
        ("push, normal policy too", p[push & normal]),
        ("push only", p[push & ~normal]),
        ("after the push: 580", p[p["day"] >= "2022-07-01"])]
print(f"{'personal loans':<26}{'loans':>6}{'lent $m':>8}{'m12':>7}"
      f"{'m24':>7}{'profit $':>11}")
for name, g in rows:
    print(f"{name:<26}{len(g):>6,}{g['amount_cents'].sum() / 1e8:>8.2f}"
          f"{(g['default_mob'] <= 12).mean():>7.1%}"
          f"{(g['default_mob'] <= 24).mean():>7.1%}"
          f"{g['profit'].sum() / 100:>11,.0f}")
only = p[push & ~normal]
print(f"push only: {len(only):,} of {push.sum():,} push loans; "
      f"they lost ${-only['profit'].sum() / 100:,.0f}")
print("m12, m24: in default (2021 definition) by that month on")
print("book; profit: cash to December 2025 after funding and a")
print("running cost of 2.5% a year (Chapter 11's loan_economics)")
