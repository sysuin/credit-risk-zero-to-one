# Mark I against Mark II on everyone who applied, with true outcomes.
# timeout: 400
import json

import numpy as np

from _truth import applicants_with_truth
from ballast.config import ROOT, SEED
from ballast.scorecard import metrics, points, reject

a = applicants_with_truth()
a["mark2"] = points.load_scorecard().score(a)
rng = np.random.default_rng(SEED)


def gap(m1, m2, bad):
    return metrics.gini(m2, bad) - metrics.gini(m1, bad)


groups = {
    "booked": lambda d: d[d["known"] & d["bad"].notna()],
    "scored": lambda d: d[~d["policy"]],
    "everyone": lambda d: d,
}
print(f"{'':<20}{'n':>7}{'Mark I':>8}{'Mark II':>8}{'gain':>8}"
      f"{'95% interval':>17}")
out = {}
for split, sname in (("holdout", "holdout"), ("out_of_time", "OOT")):
    d0 = a[a["split"] == split]
    for g, pick in groups.items():
        d = pick(d0)
        y = (d["bad"] if g == "booked" else d["truth"])
        y = y.to_numpy().astype(int)
        m1, m2 = d["mark1_score"].to_numpy(), d["mark2"].to_numpy()
        g1, g2 = metrics.gini(m1, y), metrics.gini(m2, y)
        lo, hi = metrics.interval(metrics.bootstrap(
            gap, m1, m2, y, n=1000, rng=rng))
        print(f"{sname + ', ' + g:<20}{len(d):>7,}{g1:>8.3f}{g2:>8.3f}"
              f"{g2 - g1:>+8.3f}{f'{lo:+.3f} to {hi:+.3f}':>17}")
        out[f"{split}|{g}"] = {"mark1": g1, "mark2": g2,
                               "gain": [g2 - g1, lo, hi], "n": len(d)}
print()
print("approving as many as Fernhill did (scored): true bad rate")
for split, sname in (("holdout", "holdout"), ("out_of_time", "OOT")):
    d = a[(a["split"] == split) & ~a["policy"]]
    share = d["outcome"].ne("declined").mean()
    r1 = reject.approve_best(-d["mark1_score"], d["truth"], share)
    r2 = reject.approve_best(-d["mark2"], d["truth"], share)
    fern = d.loc[d["outcome"].ne("declined"), "truth"].mean()
    print(f"  {sname:<8} {share:.1%}: Mark I {r1:.2%}, "
          f"Mark II {r2:.2%}, Fernhill {fern:.2%}")
    out[f"{split}|approve"] = {"share": share, "mark1": r1,
                               "mark2": r2, "fernhill": fern}
(ROOT / "code" / "09" / "11_a_fairer_test.json").write_text(
    json.dumps(out, indent=1) + "\n")
