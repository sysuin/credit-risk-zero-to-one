# Two ways to turn Mark II-R's score into a first-year PD, fitted on
# recent loans and tested on the next year's.
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fernhill
from ballast.commercial import migration as mg
from ballast.parameters import pd as pdm
from ballast.scorecard import metrics, points

con = fernhill.connect()
loans = pdm.personal_loans(con)
d = loans.open_month.dt.date
fit = loans[(d >= pdm.CALIBRATE_FROM) & (d <= pdm.CALIBRATE_TO)]
test = loans[loans.open_month.dt.year == 2024]
platt = pdm.fit_calibration(fit.score, fit.d12, "platt")
iso = pdm.fit_calibration(fit.score, fit.d12, "isotonic")
print(f"Fitted on {len(fit):,} loans opened Jul 2022-Dec 2023 "
      f"({fit.d12.sum()} defaults)")
print(f"  Platt: log odds of default = {platt.a:.3f} - "
      f"{-platt.b:.4f} x score")
print(f"         {-np.log(2) / platt.b:.1f} points double the odds "
      f"(the scale says {points.PDO})")
print(f"  isotonic: {len(set(iso.y))} steps")
print(f"Tested on {len(test):,} loans opened in 2024 "
      f"({test.d12.sum()} defaults)")

edges = [540, 560, 580, 600, 620]
models = {"Platt": platt.pd, "isotonic": iso.pd,
          "scale": points.bad_rate_at}
# each 2024 loan's band, and its PD under each of the three maps
t = test.copy()
t["band"] = metrics.bands(test.score, edges).to_numpy()
for k, f in models.items():
    t[k] = f(test.score)
print(f"\n{'band':<9}{'loans':>6}{'def':>5}{'observed':>10}"
      f"{'Platt':>8}{'isotonic':>10}{'scale':>8}")
rows = []
order = t.groupby("band").score.min().sort_values().index
for b in order:
    g = t[t.band == b]
    print(f"{b:<9}{len(g):>6,}{g.d12.sum():>5}{g.d12.mean():>10.2%}"
          f"{g.Platt.mean():>8.2%}{g.isotonic.mean():>10.2%}"
          f"{g.scale.mean():>8.2%}")
    lo, hi = mg.interval(int(g.d12.sum()), len(g))
    row = {"band": b, "observed": g.d12.mean(), "lower": lo,
           "upper": hi}
    for k in models:
        row[k] = g[k].mean()
    rows.append(row)

print(f"\n{'':<10}{'fit sample':>22}{'2024 loans':>24}")
print(f"{'':<10}{'mean':>8}{'log loss':>9}{'HL p':>6}"
      f"{'mean':>11}{'log loss':>9}{'HL p':>6}")
for k, f in models.items():
    out = f"{k:<10}"
    for s in (fit, test):
        p = pd.Series(np.asarray(f(s.score)), index=s.index)
        hl = metrics.hosmer_lemeshow(p, s.d12)[2]
        out += (f"{p.mean():>8.2%}{pdm.log_loss(p, s.d12):>9.4f}"
                f"{hl:>6.2f}" + " " * 3)
    print(out.rstrip())
print(f"{'observed':<10}{fit.d12.mean():>8.2%}{'':>18}"
      f"{test.d12.mean():>8.2%}")
Path(__file__).with_suffix(".json").write_text(json.dumps(
    {"bands": rows, "n": len(test)}, indent=1))
