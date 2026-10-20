# A Bayesian master scale: a prior that each grade's odds are about
# twice the one before, and 35 defaults to set the level.
import json
from pathlib import Path

import numpy as np

import fernhill
from ballast.commercial import rating as rt
from ballast.parameters import pd as pdm

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv.window_complete]
g = dev.groupby("grade").default_12m.agg(["size", "sum"])
n, d = g["size"].to_numpy(), g["sum"].to_numpy()
post = pdm.bayes_scale(n, d, g.index)
b = post.attrs["slope"]
print(f"Prior: odds x2.00 a grade (sd 0.25 on the log scale), "
      f"level open\nPosterior: odds x{np.exp(b):.2f} a grade")
print(f"\n{'grade':<6}{'n':>5}{'d':>4}{'scale':>8}{'observed':>10}"
      f"{'posterior':>11}{'90% interval':>16}")
for i, grade in enumerate(g.index):
    r = post.loc[grade]
    print(f"{grade:<6}{n[i]:>5}{d[i]:>4}{rt.pd_of(grade):>8.2%}"
          f"{d[i] / n[i]:>10.2%}{r['mean']:>11.2%}"
          f"{r.lower:>9.2%}-{r.upper:.2%}")
scale = sum(n[i] * rt.pd_of(gr) for i, gr in enumerate(g.index))
print(f"\nDefaults expected: scale {scale:.1f}, posterior "
      f"{(n * post['mean'].to_numpy()).sum():.1f}; seen {d.sum()}")
Path(__file__).with_suffix(".json").write_text(json.dumps({
    "mean": post["mean"].tolist(), "lower": post.lower.tolist(),
    "upper": post.upper.tolist()}))
