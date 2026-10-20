# timeout: 600
# Exercise 22.3: Meridian's share of the bad years at grade 7, and
# with a $40m facility at grade 5 (share of ES from its PD in the
# worst years, which is steadier than its own few defaults there).
import fernhill
import numpy as np
import pandas as pd
from ballast import capital, portfolio as pf
from ballast.commercial import rating

con = fernhill.connect()
est = pf.load_json("correlations.json")
fac = pf.load_json("factors.json")
pools, names = pf.book(con, capital.load())
lgd = pf.commercial_lgd(con)[True]
cases = [(5, 17e8), (7, 17e8), (5, 40e8)]
extra = pd.DataFrame({"company_id": [f"M{i}" for i in range(3)],
                      "grade": [g for g, _ in cases],
                      "pd": [rating.pd_of(g) for g, _ in cases],
                      "ead": [e for _, e in cases], "lgd": lgd,
                      "sector": "wholesale"})
res = pf.simulate(pools, names, pf.model_from(est, fac), extra=extra)
print(f"{'grade':>5}{'$m':>5}{'EL $':>10}{'ES share $':>13}"
      f"{'of EAD':>8}{'ES/EL':>7}")
for i, (g, e) in enumerate(cases):
    x = res.extra[:, i]
    w = res.total + x
    t = w >= np.quantile(w, 0.999)
    es = res.extra_fine[t, i].mean()
    print(f"{g:>5}{e / 1e8:>5.0f}{x.mean() / 100:>10,.0f}"
          f"{es / 100:>13,.0f}{es / e:>8.1%}{es / x.mean():>7.1f}")
