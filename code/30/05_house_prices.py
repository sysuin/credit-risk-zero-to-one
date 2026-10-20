# Fernhill's mortgage LGD and the decade it was measured in: the book's
# loan-to-value today, after the decade's worst fall, and after larger
# falls the decade never saw.
import pandas as pd

import fernhill
from ballast.config import AS_OF
from ballast.parameters import lgd

con = fernhill.connect()
est = lgd.load()["products"]["mortgage"]
idx = con.execute("SELECT month, house_price_index AS i FROM macro "
                  "ORDER BY month").df()
idx = idx.set_index(pd.to_datetime(idx["month"]))["i"]
worst = (idx / idx.cummax() - 1).min()
book = con.execute("""
    SELECT p.balance_cents AS bal, a.collateral_value_cents AS v,
           a.open_date
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.month = ? AND a.product = 'mortgage'
      AND p.status IN ('up_to_date', 'arrears', 'default')
      AND p.balance_cents > 0 ORDER BY a.account_id""", [AS_OF]).df()
opened = pd.to_datetime(book["open_date"]) + pd.offsets.MonthEnd(0)
value = book["v"] * idx.iloc[-1] / opened.map(idx).to_numpy()
bal = book["bal"].sum()
print(f"Mortgage LGD in use: {est['lgd']:.1%}, from "
      f"{est['workouts']} workouts, 2016-2025")
print(f"Worst fall in the house price index over the decade: "
      f"{worst:.1%}")
print(f"\nMortgage book, 31 Dec 2025: {len(book):,} loans, "
      f"${bal / 1e8:,.1f}m")
print(f"{'house prices':<22}{'LTV':>6}{'90%+':>8}{'100%+':>8}"
      f"{'shortfall $m':>14}")
for name, fall in (("as they are", 0.0),
                   ("the decade's worst", worst),
                   ("down 20%", -0.20), ("down 30%", -0.30)):
    ltv = book["bal"] / (value * (1 + fall))
    short = (book["bal"] - value * (1 + fall)).clip(lower=0).sum()
    print(f"{name:<22}{(ltv * book['bal']).sum() / bal:>6.0%}"
          f"{book.loc[ltv >= 0.9, 'bal'].sum() / bal:>8.1%}"
          f"{book.loc[ltv >= 1.0, 'bal'].sum() / bal:>8.1%}"
          f"{short / 1e8:>14.2f}")
print("LTV: balance-weighted; 90%+, 100%+: share of the balance;")
print("shortfall: balance above the home's value, before sale costs")
