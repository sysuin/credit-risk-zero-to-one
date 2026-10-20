# Exercise 14.4: Meridian's 2024 ratios against every commercial
# client's 2024 accounts, beside the wholesale peer group.
import fernhill
import pandas as pd
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
r = sp.ratios(sp.spread(sp.accounts(con, m)))[2024]
sectors = [x for (x,) in con.execute(
    "SELECT DISTINCT sector FROM companies ORDER BY sector").fetchall()]
whole = sp.peer_ratios(con, "wholesale", 2024, exclude=[m])
every = pd.concat(
    [sp.peer_ratios(con, x, 2024, exclude=[m]) for x in sectors])
names = ["ebitda_margin", "leverage", "interest_cover",
         "current_ratio", "receivable_days", "inventory_days",
         "cash_cycle", "cash_conversion", "cash_days", "payout"]
a = sp.compare(r, whole, names)
b = sp.compare(r, every, names)
print(f"Meridian 2024; share of peers below it "
      f"(wholesale {len(whole)}, all {len(every)})")
print(f"{'':<18}{'Meridian':>10}{'wholesale':>11}{'all':>7}"
      f"{'all median':>12}")
for n in names:
    print(f"{n:<18}{a.loc[n, 'value']:>10.2f}"
          f"{a.loc[n, 'share_below']:>11.0%}"
          f"{b.loc[n, 'share_below']:>7.0%}{b.loc[n, 'median']:>12.2f}")
