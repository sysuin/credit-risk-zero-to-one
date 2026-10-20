# How much could Fernhill lose? Every answer Ballast already holds,
# set against the capital that would have to absorb it.
import json
from pathlib import Path

import fernhill
from ballast import appetite as ap

con = fernhill.connect()
cap = ap.capital_now(con)
L = ap.losses()
m = 1e8
spare = cap["cet1"] - cap["requirement"] * cap["sa_rwa"]
print(f"{'measure':<29}{'loss':>9}{'of CET1':>9}{'CET1 used':>11}")
for _, row in L.iterrows():
    stressed = row.cet1_used == row.cet1_used
    used = f"{row.cet1_used / m:>11,.1f}" if stressed else f"{'':>11}"
    share = f"{row.loss / cap['cet1']:>9.0%}"
    if row.measure == "provision held":
        share = f"{'held':>9}"
    print(f"{row.measure:<29}{row.loss / m:>9,.1f}{share}{used}"
          .rstrip())
print("$m; the stresses' CET1 used is to the lowest point of three")
print("years, after income and the change in provisions")
print(f"\nCET1 ${cap['cet1'] / m:,.1f}m on standardised RWA of "
      f"${cap['sa_rwa'] / m:,.0f}m: {cap['cet1_ratio']:.1%}")
print(f"requirement with buffers {cap['requirement']:.1%}: "
      f"${cap['requirement'] * cap['sa_rwa'] / m:,.1f}m; above it "
      f"${spare / m:,.1f}m")

Path(__file__).with_suffix(".json").write_text(json.dumps({
    "rows": [{"measure": r.measure, "loss": r.loss / m,
              "used": (r.cet1_used / m if r.cet1_used == r.cet1_used
                       else None)} for _, r in L.iterrows()],
    "cet1": cap["cet1"] / m, "spare": spare / m}, indent=1))
