# Exercise 10.4: does the top reason survive a change of seed?
# timeout: 300
import datetime as dt

import fernhill
from ballast import data
from ballast.config import SEED
from ballast.models import gbm, reasons
from ballast.scorecard import sample

s = sample.load_sample()
apps = data.load_applications(fernhill.connect())
d = apps[(apps["product"] == "personal")
         & (apps["decline_reason"] == "score_below_cutoff")
         & (apps["app_date"] >= dt.date(2024, 1, 1))
         & (apps["app_date"] <= dt.date(2024, 6, 30))]
x = sample.characteristics(d, s.attrs["bureau_map"])
print(f"declined below the cut-off, January-June 2024: {len(x):,}")

top, two = {}, {}
for k in range(6):
    m = gbm.fit(s, seed=SEED + k)
    g = reasons.grouped(reasons.in_points(m, x), x)
    order = g.to_numpy().argsort(axis=1)
    names = g.columns.to_numpy()
    top[k] = names[order[:, 0]]
    two[k] = [frozenset(r) for r in names[order[:, :2]]]

print(f"{'seed':>6}{'top reason differs':>20}{'top two differ':>16}")
for k in range(1, 6):
    a = (top[k] != top[0]).mean()
    b = sum(p != q for p, q in zip(two[k], two[0])) / len(x)
    print(f"{SEED + k:>6}{a:>20.1%}{b:>16.1%}")
