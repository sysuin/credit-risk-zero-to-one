# Three opinions on the same reviews: Ballast's model (each year scored
# by a model fitted without it), Fernhill's model grade, and the
# analysts' grade. Which ranks the defaults better, and which sees
# them earlier?
import numpy as np

import fernhill
from ballast.commercial import rating as rt
from ballast.config import SEED
from ballast.scorecard import metrics as mt

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv.window_complete].copy()
F, y = rt.features(dev), dev.default_12m
model = rt.load_model()
dev["cv_pd"] = rt.cross_validate(F, y, dev.review_date.dt.year,
                                 model.penalty)
dev["cv_grade"] = rt.grade_of(dev.cv_pd)
views = [("cv_pd", "Ballast PD"), ("cv_grade", "Ballast grade"),
         ("model_grade", "Fernhill model grade"),
         ("grade", "analysts' grade")]


def gini_of(score, bad):
    """Gini of a score where a higher value means riskier."""
    return mt.gini(-score, bad)


def gain_over(score, analysts, bad):
    """How much better a score ranks than the analysts' grade."""
    return gini_of(score, bad) - gini_of(analysts, bad)


rng = np.random.default_rng(SEED)
print(f"{len(dev):,} reviews, {y.sum()} defaults: Gini with its 95%"
      " interval")
print(f"{'':<22}{'Gini':>7}{'interval':>16}{'gain':>8}{'P>0':>6}")
for col, label in views:
    g = gini_of(dev[col], y)
    draws = mt.bootstrap(gini_of, dev[col], y, n=500, rng=rng)
    lo, hi = mt.interval(draws)
    if col == "grade":
        print(f"{label:<22}{g:>7.3f}{lo:>9.3f} {hi:>6.3f}")
        continue
    # paired draws: the same resampled reviews for both opinions
    diff = mt.bootstrap(gain_over, dev[col], dev.grade, y,
                        n=500, rng=rng)
    print(f"{label:<22}{g:>7.3f}{lo:>9.3f} {hi:>6.3f}"
          f"{g - gini_of(dev.grade, y):>+8.3f}"
          f"{(diff > 0).mean():>6.0%}")

# The defaulters' reviews, counted back from the default.
d = rv[rv.default_month.notna()].copy()
d["before"] = (d.groupby("company_id").review_date
               .rank(ascending=False).astype(int))
d = d.merge(dev[["company_id", "review_date", "cv_grade"]],
            how="left", on=["company_id", "review_date"])
print("\nshare of the 35 defaulters graded 8 or worse (PD 5%+)")
print(f"{'reviews before default':<24}{'n':>4}{'Ballast':>9}"
      f"{'Fernhill':>10}{'analysts':>10}")
for k in (1, 2, 3):
    g = d[d.before == k]
    print(f"{k:<24}{len(g):>4}{(g.cv_grade >= 8).mean():>9.0%}"
          f"{(g.model_grade >= 8).mean():>10.0%}"
          f"{(g.grade >= 8).mean():>10.0%}")
print(f"{'all reviews (2017-24)':<24}{len(dev):>4}"
      f"{(dev.cv_grade >= 8).mean():>9.0%}"
      f"{(dev.model_grade >= 8).mean():>10.0%}"
      f"{(dev.grade >= 8).mean():>10.0%}")
g = d[d.before == 1]
print(f"median grade at the last review: Ballast "
      f"{g.cv_grade.median():.0f}, Fernhill "
      f"{g.model_grade.median():.0f}, analysts {g.grade.median():.0f}")
