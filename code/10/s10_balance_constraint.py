# Exercise 10.3: constrain card balances so that more never helps.
import numpy as np

from ballast.models import gbm
from ballast.scorecard import metrics, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"]
oot = det[det["split"] == "out_of_time"]
models = {"as built": gbm.fit(s),
          "balance +1": gbm.fit(
              s, monotone=gbm.MONOTONE | {"revolving_balance": +1})}
grid = [0, 2000, 5000, 7200, 10000, 15000, 25000]
print(f"{'':<12}{'holdout':>9}{'out of time':>13}"
      f"{'balance splits':>16}")
for name, m in models.items():
    sc = m.score(det)
    g = [metrics.gini(sc[det["split"] == k],
                      det.loc[det["split"] == k, "bad"])
         for k in ("holdout", "out_of_time")]
    used = dict(zip(m.features, m.booster.feature_importance("split")))
    print(f"{name:<12}{g[0]:>9.3f}{g[1]:>13.3f}"
          f"{used['revolving_balance']:>16}")
print()
print("average score with the balance set for everyone (out of time)")
print(f"{'balance':>9}" + "".join(f"{k:>12}" for k in models))
pd_ = {k: gbm.partial_dependence(m, oot, "revolving_balance", grid)
       for k, m in models.items()}
factor, offset = 20 / np.log(2), 600 - 20 / np.log(2) * np.log(50)
for v in grid:
    print(f"{v:>9,}" + "".join(
        f"{offset - factor * pd_[k][v]:>12.1f}" for k in models))
