# Exercise 5: the commercial provision with Chapter 18's Bayesian PDs
# for year one in place of the master scale.
# timeout: 300
import fernhill
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
r = ecl.run(con, ecl.AS_OF, params)
cp = dict(params["commercial"])
cp["master_scale"] = cp["bayes_mean"]
b = ecl.run(con, ecl.AS_OF, dict(params, commercial=cp))
for name, x in (("master scale", r), ("Bayesian", b)):
    c = x[x["segment"] == "commercial"]
    print(f"{name:<14}stage 2 {(c['stage'] == 2).sum():>4}  "
          f"provision ${c['ecl'].sum() / 1e8:,.1f}m")
