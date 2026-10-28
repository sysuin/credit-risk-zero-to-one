# Exercise 17.1: the default point with none, half or all of the
# long-term debt, and what it does to Alder Oak and to the ranking.
# timeout: 300
import datetime as dt

import pandas as pd

import fernhill
from _listed import next_year
from ballast import market as mk
from ballast.scorecard import metrics as mt

con = fernhill.connect()
cid = con.execute("SELECT company_id FROM companies "
                  "WHERE name = 'Alder Oak Materials'").fetchone()[0]
d = con.execute("SELECT company_id, default_month "
                "FROM corporate_defaults").df()
d["default_month"] = d.default_month.dt.date
print(f"{'long-term weight':<18}{'Alder Oak DD':>14}{'PD':>8}"
      f"{'assets':>9}{'March AUC':>11}")
for w in (0.0, 0.5, 1.0):
    p = mk.merton_panel(con, weight=w).merge(d, on="company_id",
                                             how="left")
    # Months from each month end to the company's default.
    month = pd.to_datetime(p.month)
    default = pd.to_datetime(p.default_month)
    p["before"] = ((default.dt.year - month.dt.year) * 12
                   + (default.dt.month - month.dt.month))
    s = next_year(p)
    march = s[[x.month == 3 for x in s.month]]
    a = p[(p.company_id == cid) & (p.month == dt.date(2020, 9, 30))]
    print(f"{w:<18.1f}{a.dd.iloc[0]:>14.2f}{a.pd.iloc[0]:>8.1%}"
          f"{a.assets.iloc[0] / 1e6:>9.2f}"
          f"{mt.auc(march.dd, march.y):>11.3f}")
