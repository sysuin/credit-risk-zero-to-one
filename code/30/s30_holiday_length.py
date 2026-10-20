# Exercise 30.2: holiday takers' defaults by the length of the holiday,
# per 1,000 accounts open on 31 December 2019.
import pandas as pd

import fernhill
from ballast import collections as coll
from ballast import performance as perf

con = fernhill.connect()
hol = coll.holidays(con)
eps = perf.default_episodes(con, "dod2021")
eps["q"] = pd.PeriodIndex(pd.to_datetime(eps["default_month"]),
                          freq="Q")
base = con.execute("""
    SELECT account_id FROM performance
    WHERE month = DATE '2019-12-31' AND status IN ('up_to_date',
          'arrears') AND product IN ('personal', 'card', 'auto',
          'mortgage') ORDER BY 1""").df()["account_id"]
groups = {m: base[base.isin(hol.loc[hol["months"] == m, "account_id"])]
          for m in (3, 6)}
quarters = pd.period_range("2020Q1", "2021Q4", freq="Q")
print(f"{'quarter':<9}{'3 months':>10}{'6 months':>10}")
tot = {3: 0.0, 6: 0.0}
for q in quarters:
    e = eps[eps["q"] == q]["account_id"]
    v = {m: e.isin(g).sum() / len(g) * 1000 for m, g in groups.items()}
    if q >= pd.Period("2020Q2"):
        tot = {m: tot[m] + v[m] for m in v}
    print(f"{str(q):<9}{v[3]:>10.1f}{v[6]:>10.1f}")
print(f"{'Q2-Q4 *':<9}{tot[3]:>10.1f}{tot[6]:>10.1f}")
print("* 2020Q2 to 2021Q4 together")
print(f"accounts: 3 months {len(groups[3]):,}, "
      f"6 months {len(groups[6]):,}")
