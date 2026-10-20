# Is Ballast's model calibrated? Out-of-sample PDs by master-scale
# grade against what happened, and the average PD year by year.
import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete").copy()
F, y = rt.features(dev), dev.default_12m
model = rt.load_model()
dev["cv_pd"] = rt.cross_validate(F, y, dev.review_date.dt.year,
                                 model.penalty)
dev["cv_grade"] = rt.grade_of(dev.cv_pd)
t = mg.default_rates(dev, "cv_grade")
mean_pd = dev.groupby("cv_grade").cv_pd.mean()
print("Ballast grade (out of sample) against what happened")
print(f"{'grade':<7}{'reviews':>8}{'mean PD':>9}{'expected':>10}"
      f"{'defaults':>10}{'observed':>10}")
for g, r in t.iterrows():
    if r.n == 0:
        continue
    exp = mean_pd[g] * r.n
    print(f"{g:<7}{r.n:>8.0f}{mean_pd[g]:>9.2%}{exp:>10.1f}"
          f"{r.defaults:>10.0f}{r.observed:>10.1%}")
print(f"{'all':<7}{len(dev):>8,}{dev.cv_pd.mean():>9.2%}"
      f"{dev.cv_pd.sum():>10.1f}{y.sum():>10}{y.mean():>10.1%}")

print("\nyear by year: average PD (out of sample) and default rate")
print(f"{'review':<8}{'mean PD':>9}{'defaults':>10}{'rate':>8}")
for yr, g in dev.groupby(dev.review_date.dt.year):
    print(f"{yr:<8}{g.cv_pd.mean():>9.2%}{g.default_12m.sum():>10}"
          f"{g.default_12m.mean():>8.1%}")
