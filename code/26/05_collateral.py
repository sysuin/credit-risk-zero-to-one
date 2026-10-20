# Loss given default under the scenarios: homes and cars through their
# price indices, unsecured loans through fewer cures.
# timeout: 300
import numpy as np

import fernhill
from ballast import stress

con = fernhill.connect()
inp = stress.inputs(con)
paths = stress.paths(con)
s0 = inp["start"]
lgd = inp["params"]["lgd"]
m = inp["mortgages"][~inp["mortgages"].in_default.astype(bool)]
ltv = m.balance_cents / m.value_cents
w = m.balance_cents / m.balance_cents.sum()
print(f"Mortgages: {len(m):,}, indexed LTV {np.sum(w * ltv):.0%} "
      "(balance-weighted)")
today = stress.mortgage_model(inp, s0["hpi"])
print(f"collateral model today {today:.2%}; Chapter 20's LGD "
      f"{lgd.loc['mortgage', 'lgd']:.2%}")
print(f"{'house prices':<22}{'fall':>7}{'LTV':>6}{'>100%':>8}"
      f"{'LGD':>8}")
cases = [(k, paths[k].hpi.min()) for k in ("base", "severe",
                                          "stress_2026")]
cases += [("hypothetical", s0["hpi"] * 0.6),
          ("hypothetical", s0["hpi"] * 0.5)]
for name, hpi in cases:
    x = ltv * s0["hpi"] / hpi
    print(f"{name:<22}{hpi / s0['hpi'] - 1:>+7.1%}{np.sum(w * x):>6.0%}"
          f"{np.sum(w * (x > 1)):>8.1%}"
          f"{stress.mortgage_lgd(inp, hpi):>8.2%}")

c = inp["cars"][~inp["cars"].in_default.astype(bool)]
cl = c.balance_cents / c.value_cents
wc = c.balance_cents / c.balance_cents.sum()
print(f"\nCar loans: {len(c):,}, indexed LTV {np.sum(wc * cl):.0%}")
print(f"Chapter 20's LGD {lgd.loc['auto', 'lgd']:.1%}, downturn "
      f"{lgd.loc['auto', 'downturn']:.1%}; by used-car prices:")
for k in ("base", "severe", "stress_2026"):
    car = paths[k].car.min()
    print(f"  {k:<20}{car / s0['car'] - 1:>+7.1%}  LGD "
          f"{stress.car_lgd(inp, car):.1%}")

print("\nUnsecured: LGD as cures fall with unemployment (Chapter 25)")
print(f"{'':<14}{'cure':>6}{'LGD':>7}{'downturn':>9}{'at 8.80%':>9}"
      f"{'at 9.82%':>9}")
for p in stress.CURED:
    print(f"{p:<14}{inp['cure'][p]:>6.1%}{lgd.loc[p, 'lgd']:>7.1%}"
          f"{lgd.loc[p, 'downturn']:>9.1%}"
          f"{stress.cure_lgd(inp, p, 8.80):>9.1%}"
          f"{stress.cure_lgd(inp, p, 9.82):>9.1%}")
