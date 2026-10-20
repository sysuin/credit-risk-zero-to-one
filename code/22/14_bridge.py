# timeout: 600
# From Chapter 21's regulatory capital to Ballast's economic capital,
# one difference at a time, for the exposures not yet in default.
import json

import fernhill
import numpy as np
from ballast import capital, portfolio as pf
from ballast.config import ROOT
from ballast.parameters import ead as eadm
from ballast.parameters import lgd as lgdm

con = fernhill.connect()
est = pf.load_json("correlations.json")
fac = pf.load_json("factors.json")
everything = capital.load()
r = everything[~everything.in_default.astype(bool)].copy()
pools, names = pf.book(con, r)
model = pf.model_from(est, fac)
steps = [("Chapter 21's IRB capital", 0.08 * r.irb_rwa.sum())]

# 1. One year, no maturity adjustment: the formula and nothing else.
rho_reg = capital.correlation(r.pd_floored, r.cls, r.sales_m)
share = 1 - r.guaranteed
steps.append(("one year, no maturity adjustment", pf.asrf_capital(
    r.irb_ead * share, r.lgd, r.pd_floored, rho_reg)))

# 2. Fernhill's own evidence: no floors, measured LGDs, the 0.76 CCF.
dt = {k: v["downturn"] for k, v in lgdm.load()["products"].items()}
ccf = eadm.load()["ccf"]["revolver"]
lg = np.where(r.segment == "commercial",
              names.set_index("company_id").lgd.reindex(r.company_id),
              r["product"].map(dt))
ead = np.where(r["product"] == "commercial_revolver",
               capital.irb_ead(r, revolver_ccf=ccf),
               r.irb_ead)
steps.append(("Fernhill's own LGD, EAD and PD",
              pf.asrf_capital(ead, lg, r["pd"], rho_reg)))

# 3. Fernhill's own correlations, still one factor and slivers.
seg = np.where(r.segment == "commercial", "companies", r["product"])
rho_own = [model.of(s)[0] for s in seg]
steps.append(("Fernhill's own correlations",
              pf.asrf_capital(ead, lg, r["pd"], rho_own)))

# 4.-6. LGD moving with the economy; many factors; names as lumps.
el = pf.expected_loss(pools, names)
steps.append(("LGD that rises in bad years",
              pf.one_factor_loss(pools, names, model) - el))
res = pf.simulate(pools, names, model)
steps.append(("a factor for each segment",
              np.quantile(res.fine, 0.999) - res.fine.mean()))
steps.append(("names as lumps: economic capital", res.ec()))

print(f"{'':<36}{'capital $m':>11}{'change':>9}")
for i, (label, v) in enumerate(steps):
    d = "" if i == 0 else f"{(v - steps[i - 1][1]) / 1e8:>+9.1f}"
    print(f"{label:<36}{v / 1e8:>11.1f}{d}")
retail = res.total - res.by_segment.companies.to_numpy()
print(f"retail alone ${res.ec(x=retail) / 1e8:.1f}m; standardised "
      f"capital, 8% of SA RWA, ${0.08 * r.sa_rwa.sum() / 1e8:,.1f}m")
cap = capital.bank_capital(con)
total = (everything.sa_rwa.sum() + cap["operational_rwa"]
         + cap["market_rwa"])
need = capital.requirements()["cet1"] * total
spare = cap["cet1"] - need
print(f"CET1 ${cap['cet1'] / 1e8:,.1f}m; required with buffers "
      f"${need / 1e8:,.1f}m; above it ${spare / 1e8:,.1f}m")
print(f"economic capital is {res.ec() / cap['cet1']:.0%} of CET1")
json.dump([[k, v / 1e8] for k, v in steps],
          open(ROOT / "code/22/14_bridge.json", "w"))
