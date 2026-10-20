# Exercise 5: the November 2023 sale valued under kinder assumptions
# for keeping: no premium on the discount rate, and the tail doubled.
import datetime as dt

import pandas as pd

import fernhill
from ballast import collections as coll

con = fernhill.connect()
sale = dt.date(2023, 11, 30)
wide = coll.sale_pool(con, sale, min_age=6, max_age=120)
pool = wide[wide["age_months"] <= wide.loc[wide["sold"],
                                           "age_months"].max()]
kept = pool[~pool["sold"]]
owed = kept["owed_cents"].sum()
f = coll.later_flows(con, kept["account_id"], sale)
m = pd.to_datetime(f["month"])
f["t"] = (m.dt.year - sale.year) * 12 + m.dt.month - sale.month
last = int(f["t"].max())
s12 = f.loc[f["t"] > last - 12, "net_cents"].sum()
p12 = f.loc[f["t"].between(last - 23, last - 12), "net_cents"].sum()
r = s12 / p12
cof = con.execute("SELECT cost_of_funds_pct FROM market_rates "
                  "WHERE month = ?", [sale]).fetchone()[0]
print(f"cost of funds {cof:.2f}%")
for premium in (5, 0):
    rate = (cof + premium) / 100
    pv = coll.present_value(f["net_cents"], f["t"], rate) / owed
    for scale in (1, 2):
        tail = scale * s12 * r / (1 - r) / owed
        tail_pv = tail / (1 + rate) ** ((last + 12) / 12)
        print(f"  discount {100 * rate:.2f}%, tail x{scale}: keeping "
              f"worth {100 * (pv + tail_pv):.2f} cents")
