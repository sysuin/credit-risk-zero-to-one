# Exercise 18.4: Pluto-Tasche for grades 1-6 at other confidence
# levels and correlations, and the Bayesian scale with other priors.
import numpy as np

import fernhill
from ballast.commercial import rating as rt
from ballast.config import SEED
from ballast.parameters import pd as pdm

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete")
g = dev[dev.grade <= 6].groupby("grade").default_12m.agg(["size",
                                                          "sum"])
n, d = g["size"].to_numpy(), g["sum"].to_numpy()
runs = {"75%": pdm.pluto_tasche(n, d, 0.75),
        "90%": pdm.pluto_tasche(n, d, 0.90),
        "95%": pdm.pluto_tasche(n, d, 0.95),
        "rho .12": pdm.pluto_tasche(n, d, 0.9, 0.12, 8, 2000, SEED),
        "rho .24": pdm.pluto_tasche(n, d, 0.9, 0.24, 8, 2000, SEED)}
print("Most prudent PDs; the two rho columns are at 90%")
print(f"{'grade':<6}{'scale':>7}" + "".join(f"{k:>9}" for k in runs))
for i, grade in enumerate(g.index):
    print(f"{grade:<6}{rt.pd_of(grade):>7.2%}"
          + "".join(f"{v[i]:>9.2%}" for v in runs.values()))

# The Bayesian scale on the whole book with a narrower and a wider
# prior on the slope.
g = dev.groupby("grade").default_12m.agg(["size", "sum"])
print(f"\n{'prior sd':<10}{'slope':>7}{'grade 1':>9}{'grade 6':>9}"
      f"{'grade 10':>10}{'expected':>10}")
for sd in (0.10, 0.25, 0.50):
    post = pdm.bayes_scale(g["size"], g["sum"], g.index,
                           slope=(np.log(2), sd))
    exp = (g["size"] * post["mean"]).sum()
    print(f"{sd:<10.2f}{np.exp(post.attrs['slope']):>7.2f}"
          f"{post.loc[1, 'mean']:>9.3%}{post.loc[6, 'mean']:>9.2%}"
          f"{post.loc[10, 'mean']:>10.2%}{exp:>10.1f}")
