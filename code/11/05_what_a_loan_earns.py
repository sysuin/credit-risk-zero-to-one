# What a good personal loan earns and a bad one costs, from Fernhill's
# own cash, and the odds at which an approval pays for itself.
import numpy as np

import fernhill
from ballast.decision import strategy
from ballast.scorecard import points, sample

con = fernhill.connect()
eco = strategy.loan_economics(con, "personal", opex_pct=2.5)
s = sample.load_sample()
s = s[s["app_date"].astype(str).between("2019-01-01", "2021-12-31")]
d = s[["account_id", "outcome"]].merge(eco, on="account_id")
d["costs"] = d["funding"] + d["opex"]
d["back"] = d["profit"] + d["amount_cents"] + d["costs"]
print("Personal loans applied for 2019-2021, to December 2025")
print(f"  {'outcome':<15}{'loans':>6}{'lent':>9}{'back':>9}"
      f"{'costs':>8}{'profit':>9}")
for out in ("good", "indeterminate", "bad"):
    g = d[d["outcome"] == out]
    print(f"  {out:<15}{len(g):>6,}"
          + "".join(f"{g[c].mean() / 100:>{w},.0f}" for c, w in
                    (("amount_cents", 9), ("back", 9), ("costs", 8),
                     ("profit", 9))))
print("  (averages per loan, in dollars; back = everything repaid,"
      "\n   recovered or still owed on a loan still open)")
print(f"  still open in December 2025: "
      f"{d['close_reason'].isna().mean():.1%}")

good = d.loc[d["outcome"] == "good", "profit"].mean()
bad = -d.loc[d["outcome"] == "bad", "profit"].mean()
odds, rate = strategy.break_even(good, bad)
score = points.score_from_log_odds(np.log(odds))
print(f"\nOne bad loan costs what {odds:.1f} good loans earn.")
print(f"Break-even: odds of {odds:.1f} to 1, a bad rate of {rate:.1%},")
print(f"which Mark II's scale puts at {float(score):.0f} points.")
