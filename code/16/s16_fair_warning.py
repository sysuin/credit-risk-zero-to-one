# Exercise 16.2: early warning with the same number of flags. In each
# review year, flag the riskiest 15% of clients by each opinion.
import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv.window_complete].copy()
model = rt.load_model()
dev["cv_pd"] = rt.cross_validate(rt.features(dev), dev.default_12m,
                                 dev.review_date.dt.year,
                                 model.penalty)
# ties in a grade are broken by the model's PD, so each flags 15%
dev["r_ballast"] = dev.cv_pd
dev["r_fernhill"] = dev.model_grade + dev.cv_pd
dev["r_analyst"] = dev.grade + dev.cv_pd
for k in ("ballast", "fernhill", "analyst"):
    dev[f"f_{k}"] = (dev.groupby(dev.review_date.dt.year)[f"r_{k}"]
                     .rank(pct=True) > 0.85)
d = dev[dev.default_month.notna()].copy()
d["before"] = (d.groupby("company_id").review_date
               .rank(ascending=False).astype(int))
print("defaulters flagged in the riskiest 15% of their year")
print(f"{'reviews before':<16}{'n':>4}{'Ballast':>9}{'Fernhill':>10}"
      f"{'analysts':>10}")
for k in (1, 2, 3):
    g = d[d.before == k]
    print(f"{k:<16}{len(g):>4}{g.f_ballast.mean():>9.0%}"
          f"{g.f_fernhill.mean():>10.0%}{g.f_analyst.mean():>10.0%}")
