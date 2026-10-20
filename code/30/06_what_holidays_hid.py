# What the 2020 payment holidays hid: the arrears Fernhill reported,
# the borrowers not paying as agreed, and when their defaults arrived.
import datetime as dt
import json

import pandas as pd

import fernhill
from ballast import collections as coll
from ballast import monitoring as mon
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
s = mon.stress_indicators(con, dt.date(2020, 1, 31),
                          dt.date(2021, 12, 31))
s["q"] = pd.PeriodIndex(pd.to_datetime(s["month"]), freq="Q")
qe = s.groupby("q").last()                      # each quarter's end
hol = coll.holidays(con)
eps = perf.default_episodes(con, "dod2021")
eps["q"] = pd.PeriodIndex(pd.to_datetime(eps["default_month"]),
                          freq="Q")
base = con.execute("""
    SELECT account_id FROM performance
    WHERE month = DATE '2019-12-31' AND status IN ('up_to_date',
          'arrears') AND product IN ('personal', 'card', 'auto',
          'mortgage') ORDER BY 1""").df()["account_id"]
took = base[base.isin(hol["account_id"])]
rest = base[~base.isin(hol["account_id"])]
print("Consumer book at each quarter end, and new defaults in the")
print("quarter per 1,000 accounts open on 31 December 2019")
print(f"{'':<8}{'reported':>10}{'behind or':>11}"
      f"{'defaults per 1,000':>21}")
print(f"{'quarter':<8}{'30+':>10}{'on holiday':>11}{'took':>11}"
      f"{'did not':>10}")
tot, quarters = [0.0, 0.0], []
for q, r in qe.iterrows():
    e = eps[eps["q"] == q]
    a = e["account_id"].isin(took).sum() / len(took) * 1000
    b = e["account_id"].isin(rest).sum() / len(rest) * 1000
    quarters.append((str(q), round(a, 2), round(b, 2)))
    if q >= pd.Period("2020Q2"):
        tot = [tot[0] + a, tot[1] + b]
    print(f"{str(q):<8}{r.dq30:>10.2%}{r.not_paying:>11.1%}"
          f"{a:>11.1f}{b:>10.1f}")
print(f"{'2020Q2 to 2021Q4, together':<29}{tot[0]:>11.1f}"
      f"{tot[1]:>10.1f}")
print(f"took a holiday: {len(took):,} accounts; did not: {len(rest):,}")

con.register("hol", hol)
perf_h = con.execute("""
    SELECT p.account_id, p.month, p.missed, h.last_month
    FROM performance p JOIN hol h USING (account_id)
    WHERE p.month BETWEEN h.first_month
          AND last_day(h.last_month + INTERVAL 12 MONTH)
    ORDER BY 1, 2""").df()
during = perf_h[perf_h["month"] <= perf_h["last_month"]]
after = perf_h[perf_h["month"] > perf_h["last_month"]]
n = perf_h["account_id"].nunique()
print(f"\nHoliday accounts reported 30+ days behind while on holiday:"
      f" {during.loc[during.missed >= 1, 'account_id'].nunique()}")
print(f"  in the 12 months after it ended: "
      f"{after.loc[after.missed >= 1, 'account_id'].nunique():,} "
      f"of {n:,}")
fig = {"month": [str(m)[:7] for m in s["month"]],
       "reported": [round(float(x), 5) for x in s["dq30"]],
       "not_paying": [round(float(x), 5) for x in s["not_paying"]],
       "quarters": quarters}
(ROOT / "code" / "30" / "06_what_holidays_hid.json").write_text(
    json.dumps(fig) + "\n")
