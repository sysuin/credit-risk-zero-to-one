# Income, the charge for losses, CET1 and the capital ratio, year by
# year: the trough under each scenario, standardised and IRB.
import json

import fernhill
from ballast import capital, stress

con = fernhill.connect()
s = stress.load()
y0 = s["summary"]["year_zero"]
req = capital.requirements()["cet1"]
a, b = y0["funding"]
print("Assumptions: the book of 31 Dec 2025 held constant; floating")
print("rates move with the policy rate one for one (cards, overdrafts,")
print("SME term, variable mortgages, companies); funding costs")
print(f"{a:.2f} + {b:.2f} x policy rate (fitted), anchored to today's "
      f"{y0['cof_now']:.2f}%,")
print("on everything CET1 does not fund; costs half of 2025's net")
print(f"interest income, ${y0['cost'] / 1e8:,.1f}m a year; no fees, "
      "tax or dividends.")
print(f"\n2025: NII ${y0['nii'] / 1e8:,.1f}m, CET1 "
      f"${y0['cet1'] / 1e8:,.1f}m, standardised RWA "
      f"${y0['sa_rwa'] / 1e8:,.0f}m,")
print(f"CET1 ratio {y0['cet1_sa']:.1%}; requirement with buffers "
      f"{req:.1%}")
print(f"\n{'year':<6}{'NII':>7}{'charge':>8}{'profit':>8}{'CET1 $m':>9}"
      f"{'CET1 SA':>9}{'IRB RWA':>9}{'CET1 IRB':>10}")
out = {"y0": y0, "req": req, "years": {}}
for k, g in s["years"].groupby("scenario", sort=False):
    print(k)
    for r in g.itertuples():
        print(f"{r.year:<6}{r.nii / 1e8:>7.1f}{r.charge / 1e8:>8.1f}"
              f"{r.profit / 1e8:>+8.1f}{r.cet1 / 1e8:>9,.1f}"
              f"{r.cet1_sa:>9.1%}{r.irb_rwa / 1e8:>9,.0f}"
              f"{r.cet1_irb:>10.1%}")
    cols = ["year", "cet1_sa", "cet1_irb", "cet1"]
    out["years"][k] = g[cols].to_dict("list")
print("\ntrough, standardised (IRB), and the gap to the requirement")
for k, v in s["summary"]["trough_sa"].items():
    irb = s["summary"]["trough_irb"][k]
    gap = (v - req) * y0["sa_rwa"]
    print(f"  {k:<12}{v:>7.1%} ({irb:.1%}){gap / 1e8:>+10,.0f} $m")
with open("code/26/08_capital.json", "w") as f:
    json.dump(out, f)
