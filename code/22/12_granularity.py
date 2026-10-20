# timeout: 600
# What lumps cost: the companies alone on one factor, simulated name by
# name, against the same book cut into slivers and Gordy's adjustment.

import fernhill
from ballast import capital, portfolio as pf

con = fernhill.connect()
rho = pf.load_json("correlations.json")["companies"]
pools, names = pf.book(con, capital.load())
one = pf.Model(rho={"companies": rho["rho"]}, beta={"companies": 1.0},
               lgd_link=False, name="one factor")
res = pf.simulate(pools.iloc[:0], names, one)
m = 1e8
fine = pf.one_factor_loss(pools.iloc[:0], names, one)
ga = pf.granularity_adjustment(names.ead, names.lgd, names["pd"],
                               rho["rho"])
print(f"companies alone, one factor, correlation {rho['rho']:.3f}")
print(f"  expected loss                    ${res.el() / m:>7.1f}m")
print(f"  99.9% loss, slivers (formula)    ${fine / m:>7.1f}m")
print(f"  99.9% loss, 230 names, simulated ${res.var() / m:>7.1f}m")
print(f"  the lumps add                    "
      f"${(res.var() - fine) / m:>7.1f}m")
print(f"  Gordy's adjustment says          ${ga / m:>7.1f}m")
for k in (2, 10):
    split = names.loc[names.index.repeat(k)].copy()
    split["ead"] = split.ead / k
    g = pf.granularity_adjustment(split.ead, split.lgd, split["pd"],
                                  rho["rho"])
    print(f"  ... each name split into {k:>2}: ${g / m:>7.1f}m")
