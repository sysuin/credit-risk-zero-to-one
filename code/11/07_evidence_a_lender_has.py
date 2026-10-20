# Mark I, Mark II, Mark II-R and the challenger ranked on the outcomes
# a lender can see: its booked loans, and the bureau's retro study.
# timeout: 400
import numpy as np
import pandas as pd

from ballast.config import SEED
from ballast.models import gbm
from ballast.scorecard import metrics, points, reject

a = reject.applicants()
a = a[~a["policy"]].merge(reject.retro(), on="app_id", how="left")
a["mark2"] = points.load_scorecard().score(a)
a["mark2r"] = reject.load_refit("mark2_retro_ws").scorecard().score(a)
a["gbm"] = gbm.load().score(a)
# An outcome where Fernhill booked the loan, or else where the bureau
# saw the applicant borrow elsewhere.
elsewhere = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(elsewhere, a["bad_elsewhere"], np.nan))
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
SAMPLES = {
    "booked, holdout": (a["split"] == "holdout") & a["known"],
    "booked, OOT": (a["split"] == "out_of_time") & a["known"],
    "+ retro, holdout": (a["split"] == "holdout") & (year >= 2019),
    "+ retro, 2023": (a["split"] == "out_of_time") & (year == 2023),
}
SCORES = {"Mark I": "mark1_score", "Mark II": "mark2",
          "II-R": "mark2r", "chall.": "gbm"}
PAIRS = [("II-R", "Mark I"), ("II-R", "Mark II"), ("chall.", "II-R")]
rng = np.random.default_rng(SEED)


def gain(x1, x2, y):
    return metrics.gini(x2, y) - metrics.gini(x1, y)


print(f"{'outcomes':<18}{'rows':>6}{'bads':>5}"
      + "".join(f"{k:>9}" for k in SCORES))
gains = []
for name, m in SAMPLES.items():
    d = a[m & a["seen"].notna()]
    y = d["seen"].astype(int).to_numpy()
    g = [metrics.gini(d[c], y) for c in SCORES.values()]
    print(f"{name:<18}{len(d):>6,}{y.sum():>5,}"
          + "".join(f"{v:>9.3f}" for v in g))
    for new, old in PAIRS:
        x1 = d[SCORES[old]].to_numpy()
        x2 = d[SCORES[new]].to_numpy()
        lo, hi = metrics.interval(metrics.bootstrap(gain, x1, x2, y,
                                                    n=1000, rng=rng))
        gains.append((name, f"{new} - {old}", gain(x1, x2, y), lo, hi))
print("II-R: Mark II-R; chall.: Chapter 10's challenger\n")
print("Gains, with 95% paired bootstrap intervals")
for name, pair, g, lo, hi in gains:
    print(f"  {name:<18}{pair:<17}{g:+.3f}  ({lo:+.3f} to {hi:+.3f})")
