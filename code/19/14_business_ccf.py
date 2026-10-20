# Conversion factors for small-business overdrafts and commercial
# revolvers, where the defaults are few.
import numpy as np

import fernhill
from ballast.config import SEED
from ballast.parameters import ead

con = fernhill.connect()
od = ead.ccf_sample(con, "sme_overdraft")
od = od[od["missed0"] == 0]
rv = ead.revolver_sample(con)

print(f"{'':<22}{'n':>4}{'used then':>11}{'CCF':>7}{'median':>8}"
      f"{'at default':>12}")
for name, s in (("overdrafts", od), ("revolvers", rv)):
    print(f"{name:<22}{len(s):>4}"
          f"{s['b0'].sum() / s['l0'].sum():>11.0%}"
          f"{ead.pooled_ccf(s):>7.2f}{s['ccf'].median():>8.2f}"
          f"{s['ead'].sum() / s['l0'].sum():>12.0%}")
for sec, g in rv.groupby("secured"):
    label = "  secured" if sec else "  unsecured"
    print(f"{label:<22}{len(g):>4}"
          f"{g['b0'].sum() / g['l0'].sum():>11.0%}"
          f"{ead.pooled_ccf(g):>7.2f}{g['ccf'].median():>8.2f}"
          f"{g['ead'].sum() / g['l0'].sum():>12.0%}")
print("used then: drawn over limit a year before default;")
print("at default: drawn at default over that limit")

# How uncertain is a CCF from 17 defaults? Resample them.
rng = np.random.default_rng(SEED)
boot = [ead.pooled_ccf(rv.iloc[rng.integers(0, len(rv), len(rv))])
        for _ in range(2000)]
lo, hi = np.percentile(boot, [5, 95])
print(f"\nrevolver CCF, 90% bootstrap interval: {lo:.2f} to {hi:.2f}")
print(f"smallest single revolver's CCF: {rv['ccf'].min():.2f}")
print(f"limit changed between the two dates: "
      f"{(rv['l1'] != rv['l0']).sum()} of {len(rv)}")
