# Does the engine see payment shock? Mortgages by how far the payment
# has risen since they were made: expected and actual defaults over
# the next year, from two year ends, and an overlay for 2025.
# timeout: 300
import datetime as dt

import fernhill
import pandas as pd
from ballast import ecl
from ballast import performance as perf

con = fernhill.connect()
eps = perf.default_episodes(con)
dm = pd.to_datetime(eps["default_month"])
BANDS = [0, 1.05, 1.4, 99]
NAMES = ["up to 5%", "5% to 40%", "over 40%"]


def shocked(date):
    r = ecl.run(con, date, ecl.parameters(con, date))
    pay = con.execute("""
        SELECT p.account_id, p.scheduled_cents / a.payment_cents AS rise
        FROM performance p JOIN accounts a USING (account_id)
        WHERE p.month = ? AND p.product = 'mortgage'
          AND a.payment_cents > 0""", [date]).df()
    m = r[(r["product"] == "mortgage") & (r["stage"] < 3)]
    m = m.merge(pay, on="account_id")
    m["band"] = pd.cut(m["rise"], BANDS, labels=NAMES)
    return m


rows = []
for date in (dt.date(2023, 12, 31), dt.date(2024, 12, 31)):
    m = shocked(date)
    t0 = pd.Timestamp(date)
    nxt = set(eps["account_id"][(dm > t0)
                                & (dm <= t0 + pd.DateOffset(years=1))])
    m["y"] = m["root_id"].isin(nxt)
    rows.append(m.groupby("band", observed=True).agg(
        n=("y", "size"), e=("pd12", "sum"), a=("y", "sum")))
both = rows[0] + rows[1]
print(f"{'payment rise':<14}{'loan-years':>11}{'expected':>10}"
      f"{'actual':>8}{'ratio':>7}")
for b, v in both.iterrows():
    print(f"{b:<14}{v.n:>11,.0f}{v.e:>10.1f}{v.a:>8.0f}"
          f"{v.a / v.e:>7.2f}")
print("next-year defaults from December 2023 and December 2024")

now = shocked(ecl.AS_OF)
ratio = both.loc["over 40%", "a"] / both.loc["over 40%", "e"]
hit = now[now["band"] == "over 40%"]
print(f"\n31 December 2025: {len(hit):,} mortgages paying over 40% "
      f"more, ${hit['balance_cents'].sum() / 1e8:,.0f}m")
print(f"their provision ${hit['ecl'].sum() / 100:,.0f}; overlay at "
      f"x{ratio:.2f}: +${hit['ecl'].sum() * (ratio - 1) / 100:,.0f}")
