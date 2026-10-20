# Discrimination, re-performed: Mark II-R's Gini with 95% intervals on
# every sample a lender can see, and on booked loans year by year.
# timeout: 300
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ballast.config import SEED
from ballast.scorecard import metrics, reject

a = reject.applicants()
a = a[~a["policy"]].merge(reject.retro(), on="app_id", how="left")
a["mark2r"] = reject.load_refit("mark2_retro_ws").scorecard().score(a)
seen_else = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(seen_else, a["bad_elsewhere"], np.nan))
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
hold, oot = a["split"] == "holdout", a["split"] == "out_of_time"
SAMPLES = {"booked, holdout": hold & a["known"],
           "booked, 2023-24": oot & a["known"],
           "+retro, 2019-22": hold & (year >= 2019),
           "+retro, 2023": oot & (year == 2023)}
rng = np.random.default_rng(SEED)
print(f"{'sample':<18}{'rows':>7}{'bads':>6}{'Gini':>8}"
      f"{'95% interval':>16}")
for name, m in SAMPLES.items():
    d = a[m & a["seen"].notna()]
    y = d["seen"].astype(int).to_numpy()
    lo, hi = metrics.interval(metrics.bootstrap(
        metrics.gini, d["mark2r"].to_numpy(), y, n=1000, rng=rng))
    print(f"{name:<18}{len(d):>7,}{y.sum():>6,}"
          f"{metrics.gini(d['mark2r'], y):>8.3f}"
          f"{f'{lo:.3f} to {hi:.3f}':>16}")

b = a[a["known"] & a["bad"].notna()]
by = []
print(f"\nBooked loans by year applied (fitted on 2016-2022)\n"
      f"{'year':<8}{'loans':>7}{'bads':>6}{'Gini':>8}"
      f"{'95% interval':>16}")
for yr, d in b.groupby(year[b.index]):
    y = d["bad"].astype(int).to_numpy()
    g = metrics.gini(d["mark2r"], y)
    lo, hi = metrics.interval(metrics.bootstrap(
        metrics.gini, d["mark2r"].to_numpy(), y, n=500, rng=rng))
    by.append({"year": int(yr), "gini": g, "lo": lo, "hi": hi})
    print(f"{yr:<8}{len(d):>7,}{y.sum():>6}{g:>8.3f}"
          f"{f'{lo:.3f} to {hi:.3f}':>16}")
Path(__file__).with_suffix(".json").write_text(json.dumps(by) + "\n")
