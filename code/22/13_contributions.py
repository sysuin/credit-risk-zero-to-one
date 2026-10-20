# timeout: 600
# Who is in the bad years: each sector's and name's share of expected
# shortfall, and what Meridian's $17m would add to the tail.

import fernhill
import numpy as np
import pandas as pd
from ballast import capital, portfolio as pf
from ballast.commercial import rating

con = fernhill.connect()
est = pf.load_json("correlations.json")
fac = pf.load_json("factors.json")
pools, names = pf.book(con, capital.load())
own = pf.commercial_lgd(con)
meridian = pd.DataFrame({"company_id": ["C0266"], "grade": [5],
                         "pd": [rating.pd_of(5)],
                         "ead": [1_700_000_000.0], "lgd": [own[True]],
                         "sector": ["wholesale"]})
res = pf.simulate(pools, names, pf.model_from(est, fac), extra=meridian)
_, by_name = res.contributions()
names["es"] = by_name
names["el"] = names["pd"] * names.lgd * names.ead
es = res.es()
s = names.groupby("sector")[["ead", "el", "es"]].sum()
s = s.sort_values("es", ascending=False)
print(f"{'sector':<18}{'EAD':>7}{'EL':>7}{'ES':>7}"
      "  (shares of the book's)")
for k, row in s.iterrows():
    print(f"{k:<18}{row.ead / names.ead.sum():>7.1%}"
          f"{row.el / names.el.sum():>7.1%}{row.es / es:>7.1%}")
info = dict(con.execute("SELECT company_id, name FROM companies")
            .fetchall())
top = names.sort_values("es", ascending=False).head(6)
print(f"\n{'largest in the tail':<26}{'grade':>5}{'EAD':>7}{'EL':>6}"
      f"{'ES':>7}{'ES/EAD':>8}  ($m)")
for _, row in top.iterrows():
    print(f"{info[row.company_id]:<26}{row.grade:>5.0f}"
          f"{row.ead / 1e8:>7.1f}{row.el / 1e8:>6.1f}"
          f"{row.es / 1e8:>7.1f}{row.es / row.ead:>8.1%}")
print(f"top six: {top.ead.sum() / names.ead.sum():.1%} of EAD, "
      f"{top.es.sum() / es:.1%} of ES")

x = res.extra[:, 0]
w = res.total + x
t = w >= np.quantile(w, 0.999)
print(f"\nMeridian, grade 5, $17m, LGD {own[True]:.1%}:")
print(f"  expected loss         ${x.mean() / 100:>12,.0f}")
dvar, des = res.var(x=w) - res.var(), res.es(x=w) - res.es()
print(f"  adds to 99.9% VaR     ${dvar / 100:>12,.0f}")
print(f"  adds to 99.9% ES      ${des / 100:>12,.0f}")
smooth = res.extra_fine[t, 0].mean()        # PD x loss in those years
own_es = x[t].mean()
print(f"  share of the ES, its own defaults ${own_es / 100:>10,.0f}")
print(f"  share of the ES, its PD in them   ${smooth / 100:>10,.0f}"
      f" ({smooth / 1.7e9:.1%} of EAD)")
print(f"  defaults in {(x > 0).mean():.2%} of years, "
      f"{(x[t] > 0).mean():.1%} of the worst 0.1%")
