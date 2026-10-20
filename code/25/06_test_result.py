# The 2024 collections test's result: cures and rolls in each arm,
# the difference with a 95% interval, and the same adjusted for the
# accounts' characteristics.
import json

import pandas as pd
import statsmodels.api as sm

import fernhill
from ballast import collections as coll
from ballast.config import ROOT

con = fernhill.connect()
t = coll.test_accounts(con)
outcomes = {"cured_1m": "up to date a month later",
            "cured_3m": "up to date three months later",
            "rolled_90": "90 days behind within three"}
out = {}
print(f"{'':<30}{'call':>7}{'text':>7}{'difference (95%)':>22}")
for k, name in outcomes.items():
    a, b = t.loc[t["call"] == 1, k], t.loc[t["call"] == 0, k]
    d, lo, hi = coll.diff_in_proportions(a.sum(), len(a), b.sum(),
                                         len(b))
    out[k] = {"call": a.mean(), "text": b.mean(), "d": d,
              "lo": lo, "hi": hi}
    print(f"{name:<30}{a.mean():>7.1%}{b.mean():>7.1%}"
          f"{100 * d:>+8.1f} ({100 * lo:+.1f} to {100 * hi:+.1f})")
print(f"accounts: call {int((t['call'] == 1).sum()):,}, "
      f"text {int((t['call'] == 0).sum()):,}; differences in points")
nnt = 1 / out["cured_1m"]["d"]
print(f"accounts called first for one extra cure next month: {nnt:.0f}")
d3, p3 = out["cured_3m"]["d"], t["cured_3m"].mean()
need = 2 * (1.96 + 0.84) ** 2 * p3 * (1 - p3) / d3 ** 2
print(f"accounts an arm to detect {100 * d3:.1f} points at three months"
      f" (80%): {need:,.0f}")

# The same comparison with the accounts' characteristics held fixed:
# a linear probability model with robust standard errors.
x = pd.get_dummies(t["product"], prefix="p", drop_first=True,
                   dtype=float)
x["call"] = t["call"].astype(float)
for f in ["log_balance", "months_on_book", "repeat", "part_paid"]:
    x[f] = t[f].astype(float)
x["bureau"] = t["bureau_v3"].fillna(0) / 100
x["month"] = t["month"].dt.month.astype(float)
print("\nadjusted for product, balance, months on book, score,")
print("past arrears, part payment and month:")
for k, name in outcomes.items():
    r = sm.OLS(t[k].astype(float), sm.add_constant(x)).fit(
        cov_type="HC1")
    d, se = r.params["call"], r.bse["call"]
    out[k].update(adj=d, adj_lo=d - 1.96 * se, adj_hi=d + 1.96 * se)
    print(f"  {name:<30}{100 * d:>+6.1f} ({100 * (d - 1.96 * se):+.1f}"
          f" to {100 * (d + 1.96 * se):+.1f})")
out = {k: {a: round(float(b), 5) for a, b in v.items()}
       for k, v in out.items()}
out["n"] = len(t)
json.dump(out,
          open(ROOT / "code/25/06_test_result.json", "w"), indent=1)
