# Mark II against Mark I, on the same loans, with the uncertainty.
# timeout: 300
import json

import numpy as np

import fernhill
from ballast.config import ROOT, SEED
from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)
det = s[s["outcome"] != "indeterminate"].copy()
det["mark2"] = card.score(det)
con = fernhill.connect()
mk1 = con.execute("SELECT app_id, mark1_score FROM applications "
                  "WHERE product = 'personal' ORDER BY app_id").df()
det = det.merge(mk1, on="app_id", how="left", validate="1:1")
print(f"loans {len(det):,}, Mark I score missing for "
      f"{det['mark1_score'].isna().sum()}")


def gap(a, b, bad):
    return metrics.gini(b, bad) - metrics.gini(a, bad)


rng = np.random.default_rng(SEED)
print()
print(f"{'sample':<12}{'Mark I':>8}{'Mark II':>9}{'gain':>8}"
      f"{'95% interval':>18}{'II wins':>9}")
out = {}
for split in ("holdout", "out_of_time"):
    d = det[det["split"] == split]
    a = d["mark1_score"].to_numpy()
    b = d["mark2"].to_numpy()
    bad = d["bad"].to_numpy()
    g1, g2 = metrics.gini(a, bad), metrics.gini(b, bad)
    draws = metrics.bootstrap(gap, a, b, bad, n=1000, rng=rng)
    lo, hi = metrics.interval(draws)
    print(f"{split:<12}{g1:>8.3f}{g2:>9.3f}{g2 - g1:>+8.3f}"
          f"{f'{lo:+.3f} to {hi:+.3f}':>18}{(draws > 0).mean():>9.1%}")
    ci1 = metrics.interval(metrics.bootstrap(
        metrics.gini, a, bad, n=1000, rng=rng))
    ci2 = metrics.interval(metrics.bootstrap(
        metrics.gini, b, bad, n=1000, rng=rng))
    out[split] = {"mark1": [g1, ci1[0], ci1[1]],
                  "mark2": [g2, ci2[0], ci2[1]],
                  "gain": [g2 - g1, lo, hi]}

d = det[det["split"] == "out_of_time"]
n = round(0.10 * len(d))
print()
print(f"out-of-time: the lowest-scoring {n} loans (10%) on each card")
for name in ("mark1_score", "mark2"):
    low = d.sort_values([name, "app_id"]).head(n)
    print(f"  {name:<12} {low['bad'].sum():>3} of {d['bad'].sum()} "
          f"bads, bad rate {low['bad'].mean():.1%}")
r = np.corrcoef(d["mark1_score"], d["mark2"])[0, 1]
print(f"correlation of the two scores: {r:.2f}")

path = ROOT / "code" / "08" / "13_mark1_vs_mark2.json"
path.write_text(json.dumps(out, indent=1) + "\n")
