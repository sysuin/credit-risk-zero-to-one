# The same model with the economy added two ways: unemployment at the
# month end, and unemployment over the year the PD is about.
import numpy as np

import fernhill
from ballast.parameters import pd as pdm
from ballast.scorecard import metrics

con = fernhill.connect()
panel = pdm.account_months(con, pdm.personal_loans(con))
u = pdm.unemployment(con)
known = panel[panel.complete].copy()
year = known.month.dt.year
versions = {"none": None, "u now": known.month.map(u),
            "u ahead": known.u_ahead}
print(f"{'economy':<9}{'coef':>7}{'odds/pt':>8}{'gap 16-22':>10}"
      f"{'gap 23-24':>10}{'loss 23-24':>11}{'Gini':>7}")
fits = {}
for name, x in versions.items():
    frame = known.assign(u_ahead=x) if x is not None else known
    model = pdm.fit_pd_model(frame[year <= 2022], macro=x is not None)
    p = model.pd(frame)
    gap = (p.groupby(year).mean() - known.y.groupby(year).mean()).abs()
    t = year >= 2023
    coef = model.params.get("u_ahead", np.nan)
    print(f"{name:<9}{coef:>7.3f}{np.exp(coef):>8.2f}"
          f"{gap.loc[:2022].mean():>10.2%}"
          f"{gap.loc[2023:].mean():>10.2%}"
          f"{pdm.log_loss(p[t], known.y[t]):>11.5f}"
          f"{metrics.gini(-p[t], known.y[t]):>7.3f}")
    fits[name] = p

print(f"\n{'year':<6}{'u now':>7}{'u ahead':>9}{'defaulted':>11}"
      f"{'none':>8}{'u now':>8}{'u ahead':>9}")
for y in sorted(year.unique()):
    s = year == y
    print(f"{y:<6}{known.month[s].map(u).mean():>7.2f}"
          f"{known.u_ahead[s].mean():>9.2f}{known.y[s].mean():>11.2%}"
          f"{fits['none'][s].mean():>8.2%}"
          f"{fits['u now'][s].mean():>8.2%}"
          f"{fits['u ahead'][s].mean():>9.2%}")

calm = (year <= 2018) | year.between(2021, 2022)
shock = year.between(2019, 2020)
print("\nFitted without the two shock years, tested on them")
print(f"{'economy':<9}{'coef':>7}{'2019':>8}{'2020':>8}{'loss':>9}")
for macro in (False, True):
    model = pdm.fit_pd_model(known[calm], macro=macro)
    p = model.pd(known)
    coef = model.params.get("u_ahead", np.nan)
    name = "u ahead" if macro else "none"
    loss = pdm.log_loss(p[shock], known.y[shock])
    print(f"{name:<9}{coef:>7.3f}{p[year == 2019].mean():>8.2%}"
          f"{p[year == 2020].mean():>8.2%}{loss:>9.5f}")
print(f"{'defaulted':<16}{known.y[year == 2019].mean():>8.2%}"
      f"{known.y[year == 2020].mean():>8.2%}")
