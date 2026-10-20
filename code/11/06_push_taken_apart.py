# The growth push taken apart: each push loan sorted by what the normal
# policy (580, DTI 0.50) would have done with it, and what it earned.
import json

import numpy as np
import pandas as pd

import fernhill
from ballast import data
from ballast import performance as perf
from ballast.config import ROOT
from ballast.decision import policy as pol
from ballast.decision import strategy

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")
        & raw["outcome"].astype(str).eq("booked")].copy()
p["dti"] = pol.dti_at_decision(p)
p["day"] = pd.to_datetime(p["app_date"].astype("datetime64[s]"))
eco = strategy.loan_economics(con, "personal")
acc = perf.cohort_accounts(con, "personal",
                           perf.default_episodes(con, "dod2021"))
first = con.execute("""
    SELECT p.account_id, max(p.missed) >= 1 AS missed_first
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.product = 'personal'
      AND datediff('month', a.open_date, p.month) = 1
    GROUP BY 1 ORDER BY 1""").df()
rate = con.execute("SELECT account_id, rate_pct FROM accounts "
                   "WHERE product = 'personal' ORDER BY 1").df()
p = (p.merge(eco[["account_id", "amount_cents", "funding", "profit"]],
             on="account_id").merge(rate, on="account_id")
      .merge(acc[["account_id", "default_mob"]], on="account_id")
      .merge(first, on="account_id"))

s = p["mark1_score"]
GROUPS = ["approved at 580 too", "580's refer band", "below 580's band",
          "instant: 515-534", "DTI 0.50-0.55", "overrides below 515"]
p["group"] = np.select(
    [p["dti"] > 0.50, s >= 590, s >= 570, s >= 535, s >= 515],
    [GROUPS[4], GROUPS[0], GROUPS[1], GROUPS[2], GROUPS[3]], GROUPS[5])
push = p[p["day"].between("2021-02-01", "2022-06-30")]
rows = [(g, push[push["group"] == g]) for g in GROUPS]
day = p["day"]
rows += [("before: 575", p[day.between("2019-01-01", "2020-03-31")]),
         ("after: 580", p[day.between("2022-07-01", "2023-12-31")])]
print(f"{'push loans':<21}{'loans':>6}{'m12':>7}{'m18':>7}{'1st':>6}"
      f"{'each':>8}{'total':>10}")
out = []
for name, g in rows:
    m12 = (g["default_mob"] <= 12).mean()
    m18 = (g["default_mob"] <= 18).mean()
    each, total = g["profit"].mean() / 100, g["profit"].sum() / 100
    print(f"{name:<21}{len(g):>6,}{m12:>7.1%}{m18:>7.1%}"
          f"{g['missed_first'].mean():>6.1%}{each:>8,.0f}"
          f"{total:>10,.0f}")
    out.append({"group": name, "loans": len(g), "m18": round(m18, 4),
                "each": round(each, 4), "total": round(total, 2)})
print("m12, m18: in default (dod2021) by that month on book;"
      "\n1st: missed the first payment; each, total: profit in $")
extra = push[push["group"] != GROUPS[0]]
loss = -extra["profit"].sum() / 100
print(f"\nLoans only the push made: {len(extra):,} of {len(push):,}, "
      f"${extra['amount_cents'].sum() / 1e8:,.2f}m lent,"
      f"\na loss of ${loss:,.0f}")
print("\nLoans the normal policy would also have made")
for name, g in [rows[0], rows[-2], rows[-1]]:
    if name == GROUPS[0]:
        name = "push: " + name
    fund = g["funding"].sum() / g["amount_cents"].sum()
    print(f"  {name:<27} rate {g['rate_pct'].mean():5.2f}%, "
          f"funding {fund:.1%} of lent")
margin = p["mark1_score"] - p["cutoff"]
band = p[margin.between(-pol.REFER, pol.REFER - 1)
         & p["override"].isna()
         & p["day"].between("2019-01-01", "2023-12-31")]
in_push = band["day"].between("2021-02-01", "2022-06-30")
print("\nRefer-band loans booked 2019-2023, by who said yes")
for name, g in (("underwriters", band[~in_push]),
                ("instant, in the push", band[in_push])):
    print(f"  {name:<22}{len(g):>5,} loans, in default by month 12 "
          f"{(g['default_mob'] <= 12).mean():.1%}")
(ROOT / "code" / "11" / "06_push_taken_apart.json").write_text(
    json.dumps(out, indent=1) + "\n")
