# A check against what happened: the twelve-month expected loss on
# 31 December 2023 against the defaults and losses of 2024.
# timeout: 300
import datetime as dt

import fernhill
import pandas as pd
from ballast import ecl
from ballast import performance as perf
from ballast.parameters import lgd as lgdm

DATE = dt.date(2023, 12, 31)
con = fernhill.connect()
r = ecl.run(con, DATE, ecl.parameters(con, DATE))
ok = r[r["stage"] < 3]

# 2024's defaults on loans performing at the date, and their loss:
# each product's LGD for defaults of 2024 at the contract rate, the
# unfinished workouts completed by Chapter 19's recovery curve.
w = lgdm.workouts(con)
f = lgdm.cash_flows(con, w)
rates = lgdm.discount_rates(con, w, "contract")
lgd24 = {p: lgdm.estimate(g, f, rates)["by_year"]["2024"]
         for p, g in w.groupby("product")}
eps = perf.default_episodes(con)
d24 = eps[pd.to_datetime(eps["default_month"]).dt.year == 2024]
ret = ok[ok["segment"] == "retail"].merge(
    d24.drop_duplicates("account_id"), left_on="root_id",
    right_on="account_id", suffixes=("", "_d"))
ret["loss"] = ret["ead_cents_d"] * ret["product"].map(lgd24)
cl = ecl.commercial_lgd(con)
gone = con.execute("""SELECT facility_id, month FROM facility_months
                      WHERE status = 'defaulted'
                        AND year(month) = 2024""").df()
com = cl[cl["facility_id"].isin(gone["facility_id"])
         & cl["facility_id"].isin(ok["account_id"])]

print(f"{'on 31 Dec 2023':<22}{'defaults in 2024':>18}"
      f"{'loss in 2024, $m':>24}")
print(f"{'':<22}{'expected':>9}{'actual':>9}{'expected':>12}"
      f"{'actual':>12}")
groups = list(ecl.RETAIL) + ["commercial"]
for p in groups:
    if p == "commercial":
        g = ok[ok["segment"] == "commercial"]
        n, lost = len(com), (com["lgd"] * com["ead_cents"]).sum()
    else:
        g = ok[ok["product"] == p]
        hit = ret[ret["product"] == p]
        n, lost = len(hit), hit["loss"].sum()
    print(f"{p:<22}{g['pd12'].sum():>9.0f}{n:>9,}"
          f"{g['ecl12'].sum() / 1e8:>12.2f}{lost / 1e8:>12.2f}")
print("expected: weighted 12-month PD and ECL (rebuilt scenarios);")
print("actual loss: EAD at default x LGD, recent workouts completed")
