# The Vasicek distribution of a large pool's default rate, for a pool
# like Fernhill's personal loans, at three correlations.
import json

import numpy as np
from ballast import portfolio as pf
from ballast.config import ROOT
from ballast.parameters import lgd as lgdm

est = pf.load_json("correlations.json")["personal"]
p, lgd = est["p"], lgdm.load()["products"]["personal"]["lgd"]
print(f"PD {p:.2%}, LGD {lgd:.1%}; default rate in the year:")
print(f"{'correlation':<20}{'median':>8}{'1 in 100':>10}"
      f"{'1 in 1,000':>12}{'ES 99.9%':>10}{'K':>7}")
for label, rho in [("Fernhill's MLE", est["rho"]),
                   ("interval top", est["hi"]),
                   ("the rules'", est["rules"])]:
    q = [pf.vasicek_quantile(x, p, rho) for x in (0.5, 0.99, 0.999)]
    k = lgd * (q[2] - p)
    print(f"{label:<14}{rho:>6.3f}{q[0]:>8.2%}{q[1]:>10.2%}"
          f"{q[2]:>12.2%}{pf.vasicek_es(0.999, p, rho):>10.2%}"
          f"{k:>7.2%}")
mean = np.mean(pf.vasicek_quantile((np.arange(1e5) + 0.5) / 1e5, p,
                                   est["rho"]))
print(f"check: the average year at the MLE defaults at {mean:.2%}")

x = np.linspace(0.0005, 0.20, 400)
json.dump({"p": p, "x": x.tolist(),
           "pdf": {str(r): pf.vasicek_pdf(x, p, r).tolist()
                   for r in (round(est["rho"], 3), 0.04, 0.10, 0.20)},
           "q999": {str(r): float(pf.vasicek_quantile(0.999, p, r))
                    for r in (round(est["rho"], 3), 0.04, 0.10, 0.20)}},
          open(ROOT / "code/22/05_vasicek.json", "w"))
