# A discrete-time hazard model for personal loans: the chance of a
# first default each month, by months on book, score band and the
# month's unemployment, with closure as a competing exit.
import json
from pathlib import Path

import numpy as np

import fernhill
from ballast.parameters import pd as pdm

con = fernhill.connect()
d = pdm.durations(con, "personal")
pm = pdm.person_months(d, pdm.unemployment(con))
model = pdm.fit_hazard("personal", pm)
print(f"{pm.n.sum():,} loan-months in {len(pm):,} cells; "
      f"{pm.d.sum():,} defaults, {pm.c.sum():,} closures")
base = model.bands[0]
print(f"Odds of default each month, against band {base}")
for b in model.bands[1:]:
    print(f"  {b:<9}{np.exp(model.default['band_' + b]):>6.2f}")
uc = model.default["u"]
print(f"  unemployment, per point: {np.exp(uc):.2f} "
      f"(coefficient {uc:.3f}, se {model.u_bse:.3f})")

lr = pdm.long_run_unemployment(con)
print(f"\nCumulative PD at {lr:.2f}% unemployment: the model against "
      "the data")
print(f"{'':<9}{'12 months':>13}{'36 months':>14}{'60 months':>14}"
      f"{'60, u+2':>10}")
print(f"{'band':<9}" + f"{'model':>8}{'data':>6}" * 3
      + f"{'model':>10}")
out = {"bands": model.bands, "model": {}, "data": {}}
for b in model.bands:
    ts = model.term_structure(b, np.full(60, lr))
    up = model.term_structure(b, np.full(60, lr + 2))
    ci = pdm.cumulative_incidence(pdm.life_table(d[d.band == b], 60))
    row = f"{b:<9}"
    for m in (12, 36, 60):
        row += f"{ts.cumulative_pd[m - 1]:>8.1%}{ci[m]:>6.1%}"
    print(row + f"{up.cumulative_pd[59]:>10.1%}")
    out["model"][b] = ts.cumulative_pd.tolist()
    out["data"][b] = ci.tolist()
Path(__file__).with_suffix(".json").write_text(json.dumps(out))
