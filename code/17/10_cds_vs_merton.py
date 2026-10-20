# Two market views of the same companies in the same months: the
# one-year PD a CDS spread implies against Merton's risk-neutral PD.
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fernhill
from ballast import market as mk

con = fernhill.connect()
p = mk.merton_panel(con)
c = p[p.cds.notna()].copy()
c["pd_cds"] = mk.pd_from_hazard(mk.hazard_from_spread(c.cds))
rho = c[["pd", "pd_cds"]].corr(method="spearman").iloc[0, 1]
print(f"company-months with both: {len(c):,} on "
      f"{c.company_id.nunique()} companies")
hi = c[c.pd > 1e-3]
rho_hi = hi[["pd", "pd_cds"]].corr(method="spearman").iloc[0, 1]
print(f"  rank correlation of the two PDs: {rho:+.2f}; where Merton's"
      f"\n  PD is above 0.1% ({len(hi)} months): {rho_hi:+.2f}")

edges = [0, 1e-4, 1e-3, 1e-2, 0.05, 0.2, 1]
labels = ["< 0.01%", "0.01-0.1%", "0.1-1%", "1-5%", "5-20%", "> 20%"]
c["band"] = pd.cut(c.pd, edges, labels=labels)
print(f"\n{'Merton PD':<11}{'months':>7}{'CDS, bp':>9}"
      f"{'CDS PD':>9}{'Merton PD':>11}{'ratio':>7}")
for band, x in c.groupby("band", observed=True):
    ratio = (x.pd_cds / x.pd).median()
    shown = f"{ratio:>7.2f}" if ratio < 100 else f"{'-':>7}"
    print(f"{band:<11}{len(x):>7}{x.cds.median():>9.0f}"
          f"{x.pd_cds.median():>9.2%}{x.pd.median():>11.3%}{shown}")

safe = c[c.pd < 1e-4]
print(f"\nwhere Merton's PD is below 0.01%: CDS median "
      f"{safe.cds.median():.1f} bp,\n  middle half "
      f"{safe.cds.quantile(0.25):.1f} to {safe.cds.quantile(0.75):.1f}"
      f" bp, implying a PD of about {safe.pd_cds.median():.2%}")
risky = c[c.pd > 0.01]
q = (risky.pd_cds / risky.pd).quantile([0.25, 0.5, 0.75])
print(f"where it is above 1%: CDS PD / Merton PD median "
      f"{q[0.5]:.2f},\n  middle half {q[0.25]:.2f} to {q[0.75]:.2f}")

Path("code/17/10_cds_vs_merton.json").write_text(json.dumps({
    "pd": [float(x) for x in np.round(c.pd, 8)],
    "pd_cds": [float(x) for x in np.round(c.pd_cds, 8)]}))
