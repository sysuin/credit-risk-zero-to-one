# AUC, Gini and KS on Mark II's samples, with the bounds that tie them.
import numpy as np

from ballast.config import SEED
from ballast.scorecard import metrics, points, sample

s = sample.load_sample()
card = points.load_scorecard()
det = s[s["outcome"] != "indeterminate"].copy()
det["score"] = card.score(det)

print(f"{'sample':<12}{'AUC':>7}{'Gini':>7}{'KS':>7}"
      f"{'KS<=Gini':>10}{'Gini<=2KS':>11}")
for split in ("train", "holdout", "out_of_time"):
    d = det[det["split"] == split]
    a = metrics.auc(d["score"], d["bad"])
    g = 2 * a - 1
    k, _ = metrics.ks(d["score"], d["bad"])
    print(f"{split:<12}{a:>7.3f}{g:>7.3f}{k:>7.3f}"
          f"{str(k <= g):>10}{str(g <= 2 * k):>11}")

# The AUC is a count of pairs: check it by comparing every pair.
d = det[det["split"] == "out_of_time"]
good = d.loc[d["bad"] == 0, "score"].to_numpy()
bad = d.loc[d["bad"] == 1, "score"].to_numpy()
diff = good[:, None] - bad[None, :]
pairs = ((diff > 0).sum() + 0.5 * (diff == 0).sum()) / diff.size
print(f"\nout of time: {good.size:,} goods x {bad.size} bads = "
      f"{diff.size:,} pairs")
print(f"share of pairs the good wins: {pairs:.6f}")
print(f"rank formula:                 "
      f"{metrics.auc(d['score'], d['bad']):.6f}")

# The bootstrap is a simulation, so its interval moves with the seed.
sc, y = d["score"].to_numpy(), d["bad"].to_numpy()
for seed in (SEED, SEED + 1):
    for n in (200, 2000):
        draws = metrics.bootstrap(metrics.gini, sc, y, n=n,
                                  rng=np.random.default_rng(seed))
        lo, hi = metrics.interval(draws)
        print(f"seed {seed}, {n:>5,} resamples: Gini 95% interval "
              f"{lo:.3f} to {hi:.3f}")
