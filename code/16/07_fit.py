# Ballast's rating model: four inputs, a logistic regression, and a
# penalty chosen by leaving out one review year at a time.
import math

import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete")
F, y = rt.features(dev), dev.default_12m
year = dev.review_date.dt.year
path = rt.penalty_path(F, y, year, [0, 1, 3, 10, 30, 100])
print("penalty  cv log loss" + "".join(f"{rt.SHORT[n]:>10}"
                                    for n in F.columns))
for lam, r in path.iterrows():
    print(f"{lam:>7g}{r.cv_log_loss:>13.5f}"
          + "".join(f"{r[n]:>+10.3f}" for n in F.columns))
best = path.cv_log_loss.idxmin()
model = rt.fit(F, y, penalty=best)
model.note = "reviews 2017-2024, default within 12 months"
print(f"\nchosen penalty {best:g}; fitted on {model.rows:,} reviews,"
      f" {model.defaults} defaults")
print(f"{'input':<14}{'mean':>8}{'sd':>8}{'coef':>9}"
      f"{'per sd, odds x':>16}")
for n, mu, sd, b in zip(model.names, model.mean, model.scale,
                        model.coef):
    print(f"{n:<14}{mu:>8.2f}{sd:>8.2f}{b:>+9.3f}"
          f"{math.exp(b):>16.2f}")
print(f"intercept {model.intercept:+.3f}; average fitted PD "
      f"{model.pd(F).mean():.2%} against {y.mean():.2%} observed")
path = rt.save_model(model)
print(f"saved to {path.relative_to(rt.BALLAST.parent.parent)}")
