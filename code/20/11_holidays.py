# The 2020 lesson: the engine run on 31 December 2020, what it expected
# of borrowers who took a payment holiday, and what they then did.
# timeout: 300
import datetime as dt

import fernhill
import pandas as pd
from ballast import ecl
from ballast import performance as perf

DATE = dt.date(2020, 12, 31)
con = fernhill.connect()
params = ecl.parameters(con, DATE)
r = ecl.run(con, DATE, params)

# Every account that took a payment holiday, and every default of 2021.
hol = {x[0] for x in con.execute("""SELECT account_id FROM
    account_events WHERE event = 'payment_holiday_start'""").fetchall()}
eps = perf.default_episodes(con)
dm = pd.to_datetime(eps["default_month"])
d21 = set(eps["account_id"][dm.dt.year == 2021])

# The performing retail accounts, marked by holiday and by default.
x = r[(r["segment"] == "retail") & (r["stage"] < 3)].copy()
x["holiday"] = x["account_id"].isin(hol)
x["y"] = x["root_id"].isin(d21)
x["in_stage_2"] = x["stage"] == 2

print(f"scenarios moved {params['scenarios'].attrs['shift']:+.2f}"
      f" points to start at Dec 2020's unemployment")
print(f"{'retail, performing':<20}{'accounts':>9}{'stage 2':>8}"
      f"{'PD':>7}{'expected':>9}{'actual':>7}{'ratio':>7}")
# Per group: accounts, share in stage 2, mean PD, expected defaults
# (the sum of the PDs) and actual defaults.
g = x.groupby("holiday").agg(n=("y", "size"),
                             s2=("in_stage_2", "mean"),
                             pd=("pd12", "mean"), e=("pd12", "sum"),
                             a=("y", "sum"))
for k, name in ((False, "no holiday"), (True, "took a holiday")):
    v = g.loc[k]
    print(f"{name:<20}{v.n:>9,.0f}{v.s2:>8.1%}{v.pd:>7.2%}{v.e:>9.0f}"
          f"{v.a:>7.0f}{v.a / v.e:>7.2f}")

# What could be seen on the day: misses in October to December 2020
# by borrowers up to date in September and off holiday by then.
seen = con.execute("""
    WITH m AS (SELECT account_id, max(missed) AS mm FROM performance
               WHERE month BETWEEN '2020-10-31' AND '2020-12-31'
               GROUP BY 1)
    SELECT p.account_id IN (SELECT account_id FROM account_events
                            WHERE event = 'payment_holiday_start'),
           avg((coalesce(m.mm, 0) >= 1)::INT)
    FROM performance p LEFT JOIN m USING (account_id)
    WHERE p.month = '2020-09-30' AND p.status = 'up_to_date'
      AND NOT p.payment_holiday
    GROUP BY 1 ORDER BY 1""").fetchall()
miss = dict(seen)
engine = g.loc[True, "pd"] / g.loc[False, "pd"]
said = miss[True] / miss[False]
later = (g.loc[True, "a"] / g.loc[True, "e"]) / (
    g.loc[False, "a"] / g.loc[False, "e"])
print(f"\nmissed a payment in Oct-Dec 2020: holiday {miss[True]:.1%}, "
      f"others {miss[False]:.1%}")
print(f"holiday group riskier by: engine x{engine:.2f}, Oct-Dec "
      f"misses x{said:.2f}")
base = x.loc[x["holiday"], "ecl"].sum()
print(f"\nholiday group's provision ${base / 1e8:.2f}m; overlays:")
print(f"  on the day, x{said / engine:.2f}: "
      f"+${base * (said / engine - 1) / 1e8:.2f}m")
print(f"  in hindsight, x{later:.2f}: "
      f"+${base * (later - 1) / 1e8:.2f}m")
two = ecl.run(con, DATE, params, stages=pd.Series(
    2, index=x.loc[x["holiday"] & (x["stage"] == 1), "account_id"]))
extra = two["ecl"].sum() - r["ecl"].sum()
print(f"  all holiday takers in stage 2: +${extra / 1e8:.2f}m")
print(f"all performing retail: expected {x['pd12'].sum():.0f} "
      f"defaults in 2021, saw {x['y'].sum():,}")
