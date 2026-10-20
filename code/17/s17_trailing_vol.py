# Exercise 17.2: equity volatility measured from the last twelve
# monthly changes in market value, instead of the table's figure.
import numpy as np
import pandas as pd

import fernhill
from _listed import listed_panel, next_year
from ballast import market as mk
from ballast.scorecard import metrics as mt

con = fernhill.connect()
p = listed_panel(con)
m = mk.market_months(con).sort_values(["company_id", "month"])
m["ret"] = m.groupby("company_id").equity.transform(
    lambda e: np.log(e).diff())
m["trailing"] = m.groupby("company_id").ret.transform(
    lambda r: r.rolling(12).std() * np.sqrt(12))
p = p.merge(m[["company_id", "month", "trailing"]],
            on=["company_id", "month"])
p = p[p.trailing.notna()].copy()
print(f"company-months with twelve months of history: {len(p):,}")
print(f"  trailing / quoted volatility: median "
      f"{(p.trailing / p.sigma_e).median():.2f}")
out = [mk.solve_assets(e, s, d, r) for e, s, d, r in
       zip(p.equity, p.trailing, p.default_point, p.r)]
p["dd_trailing"] = [mk.distance_to_default(v, s, d, r) for (v, s, _),
                    d, r in zip(out, p.default_point, p.r)]
s = next_year(p)
march = s[[x.month == 3 for x in s.month]]
print(f"\nMarch reviews: {len(march)} company-years, "
      f"{march.y.sum()} defaults")
print(f"  AUC, quoted volatility    {mt.auc(march.dd, march.y):.3f}")
print(f"  AUC, trailing volatility  "
      f"{mt.auc(march.dd_trailing, march.y):.3f}")
cid = con.execute("SELECT company_id FROM companies "
                  "WHERE name = 'Alder Oak Materials'").fetchone()[0]
a = p[p.company_id == cid].set_index("month")
for day in pd.to_datetime(["2020-09-30", "2020-10-31"]).date:
    print(f"Alder Oak {day:%b %Y}: DD {a.dd[day]:.2f} quoted, "
          f"{a.dd_trailing[day]:.2f} trailing")
