# Exercise 16.1: the rating model with fewer inputs, scored the same
# way (each review year by a model fitted without it).
import fernhill
from ballast.commercial import rating as rt
from ballast.scorecard import metrics as mt

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete")
F, y = rt.features(dev), dev.default_12m
year = dev.review_date.dt.year
sets = [["ln_leverage"],
        ["ln_leverage", "ln_cover", "equity_ratio"],
        rt.FEATURES]
print(f"{'inputs':<34}{'penalty':>8}{'log loss':>10}{'Gini':>7}")
for cols in sets:
    best = None
    for lam in (0, 1, 3, 10, 30):
        p = rt.cross_validate(F[cols], y, year, lam)
        ll = rt.log_loss(p, y)
        if best is None or ll < best[1]:
            best = (lam, ll, mt.gini(-p, y))
    name = ", ".join(rt.SHORT[c] for c in cols)
    print(f"{name:<34}{best[0]:>8g}{best[1]:>10.5f}{best[2]:>7.3f}")
