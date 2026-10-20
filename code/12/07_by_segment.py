# The price test by channel and by score, and a logistic model of
# take-up on the randomised price change.
import sys

import numpy as np
import pandas as pd

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import mark1_tier, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
t = a[a["decision"].eq("approve") & a["app_date"].dt.year.eq(2024)
      ].copy()
t["arm"] = t["price_test_arm"].fillna("policy")
t["took"] = t["outcome"].eq("booked").astype(int)
t["change"] = t["arm"].map({"minus_150": -1.5, "policy": 0.0,
                            "plus_150": 1.5})
t["broker"] = t["channel"].eq("broker").astype(int)
t["high"] = (t["m2r"] >= 590).astype(int)

print(f"{'':<19}{'n -1.5':>7}{'took':>5}{'n +1.5':>7}{'took':>5}"
      f"{'gap':>7}{'95% interval':>16}")
segs = {"branch and online": t["broker"] == 0,
        "broker": t["broker"] == 1,
        "Mark II-R under 590": t["high"] == 0,
        "Mark II-R 590 up": t["high"] == 1}
for name, m in segs.items():
    lo = t[m & (t["arm"] == "minus_150")]["took"]
    hi = t[m & (t["arm"] == "plus_150")]["took"]
    gap = hi.mean() - lo.mean()
    se = np.sqrt(hi.var(ddof=0) / len(hi) + lo.var(ddof=0) / len(lo))
    ci = [100 * (gap + k * 1.96 * se) for k in (-1, 1)]
    print(f"{name:<19}{len(lo):>7}{lo.mean():>5.0%}{len(hi):>7}"
          f"{hi.mean():>5.0%}{100 * gap:>+7.1f}"
          f"{ci[0]:>+8.1f} to {ci[1]:+.1f}")

tier = pd.get_dummies(mark1_tier(t["mark1_score"]).array,
                      drop_first=True).astype(float)
ctrl = pd.concat([tier.reset_index(drop=True),
                  t[["broker"]].reset_index(drop=True)], axis=1)
r = pricing.fit_take_up(t["took"], t["change"], ctrl)
b, (lo, hi) = r.params["change"], r.conf_int().loc["change"]
print(f"\nLogistic model on all {len(t):,} approvals of 2024, "
      f"tier and broker held")
print(f"  log odds of taking the loan per point {b:.3f}\n"
      f"  (95% interval {lo:.3f} to {hi:.3f})")
for p0 in (0.30, 0.64, 0.90):
    up = pricing.shift_take_up(p0, b, [-1.0, 1.0])
    print(f"  from {p0:.0%} at today's price: {up[0]:.0%} a point "
          f"cheaper, {up[1]:.0%} a point dearer")
