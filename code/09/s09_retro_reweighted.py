# Exercise 9.3: correcting the retro study for who borrowed elsewhere.
import numpy as np
import pandas as pd

from _truth import applicants_with_truth
from ballast.scorecard import metrics, reject

a = applicants_with_truth()
f = reject.frames(a)
acc, unk, hold = f["accepts"], f["unknown"], f["holdout"]
base = reject.fit(acc, acc["bad"])
x = unk.merge(reject.retro(), on="app_id", how="inner")
x["band"] = np.floor(base.score(x) / 20) * 20
x["opened"] = x["opened_elsewhere"].astype(bool)
share = x.groupby(["outcome", "band"])["opened"].transform("mean")
op = x[x["opened"]].copy()
op["weight"] = 1 / share[x["opened"]]
acc1 = acc.assign(weight=1.0, bad=acc["bad"].astype(float))
dec = hold[hold["outcome"] == "declined"]
print(f"{'retro rows':<16}{'weight':>9}{'declines':>10}{'Gini':>8}")
for name, w in (("as they come", np.ones(len(op))),
                ("reweighted", op["weight"].to_numpy())):
    t = pd.concat([acc1, op.assign(bad=op["bad_elsewhere"], weight=w)],
                  ignore_index=True)
    r = reject.fit(t, t["bad"], t["weight"])
    g = metrics.gini(-r.p_bad(hold), hold["truth"].astype(int))
    print(f"{name:<16}{w.sum():>9,.0f}{r.p_bad(dec).mean():>10.1%}"
          f"{g:>8.3f}")
print(f"true bad rate of the holdout's declines: "
      f"{dec['truth'].mean():.1%}")
