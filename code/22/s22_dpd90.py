# Exercise 22.2: the personal loans' and cards' correlation when default
# means plain 90 days past due, against the 2021 definition.
import fernhill
from ballast import performance as perf
from ballast import portfolio as pf
from ballast.parameters import pd as pdm

con = fernhill.connect()
print(f"{'':<10}{'definition':<12}{'mean rate':>10}{'MLE':>7}"
      f"{'90% interval':>15}")
for d in ("dpd90", "dod2021"):
    eps = perf.default_episodes(con, d)
    r = pdm.annual_default_rates(con, eps, ["personal", "card"],
                                 pf.YEARS)
    for p, g in r.groupby("product"):
        f = pf.fit_rho(g.defaults, g.at_risk)
        band = f"{f['lo']:.3f}-{f['hi']:.3f}"
        print(f"{p:<10}{d:<12}{g.rate.mean():>10.2%}{f['rho']:>7.3f}"
              f"{band:>15}")
