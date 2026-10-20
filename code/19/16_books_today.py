# Fernhill's car and mortgage books on 31 December 2025: loan-to-value
# on indexed collateral today, and after a fall like the worst the
# decade saw.
import json

import pandas as pd

import fernhill
from ballast.config import AS_OF, ROOT

con = fernhill.connect()
macro = con.execute("SELECT month, house_price_index AS mortgage, "
                    "used_car_index AS auto FROM macro "
                    "ORDER BY month").df()
macro = macro.set_index(pd.to_datetime(macro["month"]))
fit = json.load(open(ROOT / "code/19/15_collateral.json"))["fit"]

print(f"{'':<10}{'':<12}{'LTV':>7}{'90%+':>8}{'100%+':>8}"
      f"{'car LGD':>10}")
for p in ("auto", "mortgage"):
    idx = macro[p]
    fall = (idx / idx.cummax() - 1).min()       # peak to trough
    book = con.execute("""
        SELECT p.balance_cents AS bal, a.collateral_value_cents AS v,
               a.open_date
        FROM performance p JOIN accounts a USING (account_id)
        WHERE p.month = ? AND a.product = ?
          AND p.status IN ('up_to_date', 'arrears', 'default')
          AND p.balance_cents > 0""", [AS_OF, p]).df()
    opened = pd.to_datetime(book["open_date"]) + pd.offsets.MonthEnd(0)
    value = book["v"] * idx.iloc[-1] / opened.map(idx).to_numpy()
    bal = book["bal"].sum()
    print(f"{p} ({len(book):,} loans; worst fall in the index "
          f"{fall:.1%})")
    for label, shock in (("today", 0.0), ("after fall", fall)):
        ltv = book["bal"] / (value * (1 + shock))
        line = (f"{'':<10}{label:<12}"
                f"{(ltv * book['bal']).sum() / bal:>7.0%}"
                f"{book.loc[ltv >= 0.9, 'bal'].sum() / bal:>8.1%}"
                f"{book.loc[ltv >= 1.0, 'bal'].sum() / bal:>8.1%}")
        if p == "auto":
            lgd = (fit[0] + fit[1] * ltv) * book["bal"]
            line += f"{lgd.sum() / bal:>10.1%}"
        print(line)
print("LTV: balance-weighted; 90%+, 100%+: share of the balance;")
print("car LGD: from listing 15's line, weighted by balance")
