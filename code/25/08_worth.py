# What phoning first is worth: losses in each arm a year on, the value
# of a cure from the years before the test, and the cost of the calls.
import numpy as np
import pandas as pd
import statsmodels.api as sm

import fernhill
from ballast import collections as coll
from ballast.config import SEED

con = fernhill.connect()
t = coll.test_accounts(con)
t = t.merge(coll.later_outcomes(con, t, 12), on=["root_id", "month"])
t["loss"] = (t["off_cents"] - t["rec_cents"]) / 100
print("A year after falling behind     call first  text first")
for k, name in [("reached_90", "reached 90 days"),
                ("written_off", "written off")]:
    g = t.groupby("call")[k].mean()
    print(f"  {name:<30}{g[1]:>10.1%}{g[0]:>12.1%}")
a, b = t.loc[t["call"] == 1, "loss"], t.loc[t["call"] == 0, "loss"]
rng = np.random.default_rng(SEED)
boot = [rng.choice(a.to_numpy(), len(a)).mean()
        - rng.choice(b.to_numpy(), len(b)).mean() for _ in range(2000)]
lo, hi = np.percentile(boot, [2.5, 97.5])
def usd(v):
    return f"-${-v:,.0f}" if v < 0 else f"${v:,.0f}"


print(f"  {'loss per account, to date':<30}{usd(a.mean()):>10}"
      f"{usd(b.mean()):>12}")
print(f"  difference {usd(a.mean() - b.mean())} "
      f"(bootstrap 95%: {usd(lo)} to {usd(hi)})")

h = coll.entries(con, "2022-01-01", "2023-12-31",
                 products=tuple(coll.FAMILY))
h = h.merge(coll.later_outcomes(con, h, 12), on=["root_id", "month"])
h["loss"] = (h["off_cents"] - h["rec_cents"]) / 100
raw = h.groupby("cured_1m")["loss"].mean()
x = pd.get_dummies(h["product"], drop_first=True, dtype=float)
x["cured"] = h["cured_1m"].astype(float)
x["balance"] = h["balance"]
x["log_balance"] = h["log_balance"]
x["months_on_book"] = h["months_on_book"].astype(float)
fit = sm.OLS(h["loss"], sm.add_constant(x)).fit(cov_type="HC1")
value = -fit.params["cured"]
print(f"\nEntries of 2022-2023 ({len(h):,}), loss a year on:")
print(f"  cured next month ${raw[1]:,.0f}, not cured ${raw[0]:,.0f}")
print(f"  a cure's value, product and balance held: ${value:,.0f}")

eff = coll.diff_in_proportions(
    int(t.loc[t["call"] == 1, "cured_1m"].sum()), len(a),
    int(t.loc[t["call"] == 0, "cured_1m"].sum()), len(b))
per = [e * value for e in eff]
print(f"  so phoning first is worth ${per[0]:,.0f} an account "
      f"(${per[1]:,.0f} to ${per[2]:,.0f})")

con.register("tt", t[["account_id", "month", "call"]].assign(
    month=t["month"].dt.date))
calls = con.execute("""
    SELECT tt.call, count(DISTINCT tt.account_id) AS n,
           count(*) FILTER (WHERE c.action = 'phone_call') AS calls,
           count(*) FILTER (WHERE c.action = 'sms') AS texts
    FROM tt LEFT JOIN collections c ON c.account_id = tt.account_id
     AND c.month BETWEEN tt.month
         AND last_day(tt.month + INTERVAL 5 MONTH)
    GROUP BY 1 ORDER BY 1""").df().set_index("call")
c1 = calls.loc[1, "calls"] / calls.loc[1, "n"]
c0 = calls.loc[0, "calls"] / calls.loc[0, "n"]
s0 = calls.loc[0, "texts"] / calls.loc[0, "n"]
print(f"\nCalls per account in six months: call first {c1:.2f}, "
      f"text first {c0:.2f}")
print(f"  ({s0:.2f} texts each); {c1 - c0:.2f} extra calls an account")
print(f"  break-even: an extra call may cost up to "
      f"${per[0] / (c1 - c0):,.0f}")
print(f"  (${per[1] / (c1 - c0):,.0f} at the bottom of the interval)")
n25 = len(coll.entries(con, "2025-01-01", "2025-09-30",
                       products=tuple(coll.FAMILY)))
year = n25 * 4 / 3
print(f"fresh entries, Jan-Sep 2025: {n25:,}; about {year:,.0f} a "
      "year,")
print(f"  worth about ${year * per[0]:,.0f} a year before the calls' "
      f"cost")
