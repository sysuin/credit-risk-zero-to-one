# The commercial grades, validated as a low-default portfolio: the
# ranking of three opinions with intervals, each grade's PD tested
# both ways, and the book's defaults year by year.
# timeout: 300
import numpy as np

import fernhill
from ballast import capital
from ballast import validation as vd
from ballast.commercial import rating as rt
from ballast.config import SEED
from ballast.scorecard import metrics

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete").copy()
y = dev["default_12m"].to_numpy()
dev["cv_pd"] = rt.cross_validate(rt.features(dev), dev["default_12m"],
                                 dev["review_date"].dt.year,
                                 rt.load_model().penalty)
rng = np.random.default_rng(SEED)
print(f"{len(dev):,} reviews, {y.sum()} defaults in the year after")
print(f"{'Gini':<28}{'value':>7}{'95% interval':>16}")
for name, x in (("Ballast model (out of year)", -dev["cv_pd"]),
                ("Fernhill model grade", -dev["model_grade"]),
                ("analysts' grade", -dev["grade"])):
    lo, hi = metrics.interval(metrics.bootstrap(
        metrics.gini, x.to_numpy(), y, n=1000, rng=rng))
    print(f"{name:<28}{metrics.gini(x, y):>7.3f}"
          f"{f'{lo:.3f} to {hi:.3f}':>16}")

print("\nAnalysts' grades against the master scale; one-sided p-values")
print(f"{'grade':<6}{'reviews':>8}{'PD':>7}{'seen':>5}"
      f"{'Jeffreys 95%':>15}"
      f"{'too low':>9}{'too high':>9}")
for g in rt.GRADES:
    x = dev[dev["grade"] == g]
    n, d, p = len(x), int(x["default_12m"].sum()), rt.pd_of(g)
    lo, hi = vd.jeffreys_interval(n, d)
    print(f"{g:<6}{n:>8,}{p:>7.2%}{d:>5}{f'{lo:.2%}-{hi:.2%}':>15}"
          f"{vd.jeffreys_p(n, d, p):>9.3f}"
          f"{1 - vd.jeffreys_p(n, d, p):>9.3f}")

print(f"\n{'review':<8}{'clients':>8}{'expected':>9}{'seen':>6}"
      f"{'light':>7}{'corr.':>7}")
for yr, x in dev.groupby(dev["review_date"].dt.year):
    pds = x["grade"].map(rt.pd_of)
    n, d, p = len(x), int(x["default_12m"].sum()), pds.mean()
    rho = float(np.mean(capital.correlation(pds, "corporate", 100)))
    print(f"{yr:<8}{n:>8}{pds.sum():>9.1f}{d:>6}"
          f"{vd.traffic_light(n, d, p):>7}"
          f"{vd.traffic_light(n, d, p, rho):>7}")
