# Benchmarking: Mark II-R against Mark I, Mark II and the boosted
# challenger on the fairest outcomes a lender has, booked loans plus
# the bureau's retro study, with paired 95% intervals.
# timeout: 300
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
seen_else = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(seen_else, a["bad_elsewhere"], np.nan))
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
SAMPLES = {"2019-22 holdout": (a["split"] == "holdout")
           & (year >= 2019),
           "2023": (a["split"] == "out_of_time") & (year == 2023)}
BENCH = {"Mark I": "mark1_score", "Mark II": "mark2",
         "challenger": "gbm"}
rng = np.random.default_rng(SEED)


def gain(x1, x2, y):
    return metrics.gini(x2, y) - metrics.gini(x1, y)


print("Mark II-R's Gini less each benchmark's (booked + retro)")
print(f"{'sample':<17}{'benchmark':<12}{'its Gini':>9}{'gain':>8}"
      f"{'95% interval':>18}")
for name, m in SAMPLES.items():
    d = a[m & a["seen"].notna()]
    y = d["seen"].astype(int).to_numpy()
    for k, c in BENCH.items():
        x1, x2 = d[c].to_numpy(), d["mark2r"].to_numpy()
        lo, hi = metrics.interval(metrics.bootstrap(
            gain, x1, x2, y, n=1000, rng=rng))
        print(f"{name:<17}{k:<12}{metrics.gini(x1, y):>9.3f}"
              f"{gain(x1, x2, y):>+8.3f}"
              f"{f'{lo:+.3f} to {hi:+.3f}':>18}")
