# Exercise 9.2: how much of parcelling's gain is the luck of the draw.
import numpy as np

from _truth import applicants_with_truth
from ballast.config import SEED
from ballast.scorecard import metrics, reject

a = applicants_with_truth()
f = reject.frames(a)
acc, unk, hold = f["accepts"], f["unknown"], f["holdout"]
y = hold["truth"].astype(int)
base = reject.fit(acc, acc["bad"])
g0 = metrics.gini(-base.p_bad(hold), y)
ginis = []
for k in range(10):
    t = reject.training_set("parcelling", acc, unk, base=base,
                            rng=np.random.default_rng(SEED + k))
    r = reject.fit(t, t["bad"])
    ginis.append(metrics.gini(-r.p_bad(hold), y))
g = np.array(ginis)
print(f"ignore: {g0:.3f}")
print("parcelling, ten seeds:")
print("  " + " ".join(f"{v:.3f}" for v in g))
print(f"gain: mean {g.mean() - g0:+.3f}, from {g.min() - g0:+.3f} "
      f"to {g.max() - g0:+.3f}; spread (sd) {g.std(ddof=1):.4f}")
