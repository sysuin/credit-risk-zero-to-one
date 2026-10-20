# timeout: 600
# Asset correlation by segment from nine years of default rates: the
# method of moments, maximum likelihood with a 90% interval, without
# 2020, with a drifting book, and the rules' correlation.
import json

import fernhill
from ballast import portfolio as pf
from ballast.config import ROOT

con = fernhill.connect()
est = pf.estimate(con)
print(f"{'segment':<14}{'moments':>8}{'MLE':>7}{'90% interval':>15}"
      f"{'no 2020':>8}{'drift':>7}{'rules':>7}")
for seg, e in est.items():
    band = f"{e['lo']:.3f}-{e['hi']:.3f}"
    print(f"{seg:<14}{e['mom']:>8.3f}{e['rho']:>7.3f}{band:>15}"
          f"{e['no2020']:>8.3f}{e['drift']:>7.3f}{e['rules']:>7.3f}")
print("saved:", pf.save_json(est, "correlations.json"))
json.dump(est, open(ROOT / "code/22/02_estimate.json", "w"))
