# The commercial grades against the answer: each client's true
# one-year PD at its March review, against the master scale, the
# Bayesian scale, Pluto-Tasche and what happened.
import pandas as pd

import fernhill
from ballast.commercial import rating as rt
from ballast.parameters import pd as pdm

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv.window_complete].copy()
dev["month"] = pd.to_datetime(dev.review_date)
truth = fernhill.connect(truth=True)          # the answer, read once
t = truth.execute("SELECT company_id, month, pd_1y FROM corporate_pd"
                  ).df()
t["month"] = pd.to_datetime(t.month)
dev = dev.merge(t, on=["company_id", "month"], how="left",
                validate="1:1")
g = dev.groupby("grade").agg(n=("pd_1y", "size"),
                             d=("default_12m", "sum"),
                             truth=("pd_1y", "mean"))
post = pdm.bayes_scale(g.n, g.d, g.index)["mean"]
pt = pdm.pluto_tasche(g.n, g.d, 0.9)
pt[:6] = pdm.pluto_tasche(g.n[:6], g.d[:6], 0.9)
print(f"{'grade':<6}{'n':>5}{'truth':>8}{'scale':>8}{'Bayes':>8}"
      f"{'PT 90%':>8}{'observed':>10}")
for i, (grade, r) in enumerate(g.iterrows()):
    print(f"{grade:<6}{r.n:>5.0f}{r.truth:>8.3%}{rt.pd_of(grade):>8.2%}"
          f"{post[grade]:>8.2%}{pt[i]:>8.2%}{r.d / r.n:>10.2%}")
scale = sum(r.n * rt.pd_of(k) for k, r in g.iterrows())
print(f"\nDefaults expected over {len(dev):,} reviews: truth "
      f"{dev.pd_1y.sum():.1f}, scale {scale:.1f},\nBayes "
      f"{(g.n * post).sum():.1f}, Pluto-Tasche {(g.n * pt).sum():.1f};"
      f" seen {dev.default_12m.sum()}")
print(f"\n{'review':<8}{'clients':>8}{'truth expected':>16}{'seen':>6}")
for y, s in dev.groupby(dev.month.dt.year):
    print(f"{y:<8}{len(s):>8}{s.pd_1y.sum():>16.1f}"
          f"{s.default_12m.sum():>6}")
