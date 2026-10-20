# Exercise 30.1: Fernhill's consumer products, year by year: do they
# move together more or less than its regions?
import numpy as np

import fernhill
from ballast import performance as perf
from ballast.parameters import pd as pdm

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
products = ["personal", "card", "auto", "mortgage"]
r = pdm.annual_default_rates(con, eps, products, range(2017, 2026))
w = r.pivot(index="year", columns="product", values="rate")[products]
print("Default rate by product and year, % (2021 definition)")
print(f"{'':<10}" + "".join(f"{y:>6}" for y in w.index))
for p in products:
    print(f"{p:<10}" + "".join(f"{v * 100:>6.2f}" for v in w[p]))
c = w.corr()
pairs = c.to_numpy()[np.triu_indices(len(products), 1)]
print(f"correlation of products' yearly rates, 6 pairs: "
      f"{pairs.min():.2f} to {pairs.max():.2f}")
for p in products:
    others = c[p].drop(p).mean()
    print(f"  {p:<10} worst year {int(w[p].idxmax())}, "
          f"2020 / 2019 {w.loc[2020, p] / w.loc[2019, p]:.2f}x, "
          f"mean corr {others:.2f}")
