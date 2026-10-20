# Challenger against Mark II on the same loans, with paired intervals.
# timeout: 300
import json

import numpy as np

from ballast.config import ROOT, SEED
from ballast.models import gbm
from ballast.scorecard import metrics, points, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"].copy()
det["mark2"] = points.load_scorecard().score(det)
det["challenger"] = gbm.fit(s).score(det)


def gap(a, b, bad):
    return metrics.gini(b, bad) - metrics.gini(a, bad)


rng = np.random.default_rng(SEED)
print(f"{'sample':<12}{'Mark II':>8}{'challenger':>11}{'gain':>8}"
      f"{'95% interval':>18}{'wins':>7}")
out = {}
for split in ("holdout", "out_of_time"):
    d = det[det["split"] == split]
    a, b, bad = (d["mark2"].to_numpy(), d["challenger"].to_numpy(),
                 d["bad"].to_numpy())
    g1, g2 = metrics.gini(a, bad), metrics.gini(b, bad)
    draws = metrics.bootstrap(gap, a, b, bad, n=1000, rng=rng)
    lo, hi = metrics.interval(draws)
    print(f"{split:<12}{g1:>8.3f}{g2:>11.3f}{g2 - g1:>+8.3f}"
          f"{f'{lo:+.3f} to {hi:+.3f}':>18}{(draws > 0).mean():>7.1%}")
    ci1 = metrics.interval(metrics.bootstrap(
        metrics.gini, a, bad, n=1000, rng=rng))
    ci2 = metrics.interval(metrics.bootstrap(
        metrics.gini, b, bad, n=1000, rng=rng))
    out[split] = {"mark2": [g1, *ci1], "challenger": [g2, *ci2],
                  "gain": [g2 - g1, lo, hi]}
    print(f"{'  interval':<12}{f'{ci1[0]:.2f}-{ci1[1]:.2f}':>8}"
          f"{f'{ci2[0]:.2f}-{ci2[1]:.2f}':>11}")

d = det[det["split"] == "out_of_time"]
print()
print(f"out-of-time: bads among the lowest-scoring loans "
      f"(of {d['bad'].sum()})")
print(f"{'lowest':>8}{'loans':>7}{'Mark II':>9}{'challenger':>12}")
for share in (0.05, 0.10, 0.20, 0.30, 0.50):
    n = round(share * len(d))
    caught = [d.sort_values([k, "app_id"]).head(n)["bad"].sum()
              for k in ("mark2", "challenger")]
    print(f"{share:>8.0%}{n:>7,}{caught[0]:>9}{caught[1]:>12}")
r = np.corrcoef(d["mark2"], d["challenger"])[0, 1]
print(f"correlation of the two scores: {r:.2f}")

path = ROOT / "code" / "10" / "05_honest_comparison.json"
path.write_text(json.dumps(out, indent=1) + "\n")
