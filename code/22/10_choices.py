# timeout: 900
# Economic capital under other choices: correlations at the top of
# their intervals or at the rules' values, sectors with cycles of
# their own, every segment on one factor, LGD that does not move.
import dataclasses

import fernhill
from ballast import capital, portfolio as pf

con = fernhill.connect()
est = pf.load_json("correlations.json")
fac = pf.load_json("factors.json")
pools, names = pf.book(con, capital.load())
base = pf.model_from(est, fac, "rho", "central (MLE)")
runs = [base,
        pf.model_from(est, fac, "hi", "tops of intervals"),
        pf.model_from(est, fac, "rules", "the rules'"),
        pf.with_sectors(base, names, 0.5, "sectors half their own"),
        dataclasses.replace(base, beta={k: 1.0 for k in base.beta},
                            name="one factor for all"),
        dataclasses.replace(base, lgd_link=False,
                            name="LGD fixed")]
m = 1e8
print(f"{'$m':<24}{'EL':>7}{'VaR':>8}{'ES':>8}{'EC':>8}"
      f"{'retail EC':>10}")
for model in runs:
    r = pf.simulate(pools, names, model)
    ret = r.by_segment.drop(columns="companies").sum(axis=1).to_numpy()
    print(f"{model.name:<24}{r.el() / m:>7.1f}{r.var() / m:>8.1f}"
          f"{r.es() / m:>8.1f}{r.ec() / m:>8.1f}"
          f"{r.ec(x=ret) / m:>10.1f}")
