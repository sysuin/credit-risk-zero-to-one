# The CET1 ratio Fernhill should hold, derived from its stress tests,
# and the most economic capital its common equity can carry.
import json
from pathlib import Path

import fernhill
from ballast import appetite as ap
from ballast import portfolio as pf
from ballast import stress

con = fernhill.connect()
cap = ap.capital_now(con)
s = stress.load()["summary"]
t = ap.capital_target(cap, s)
m, rwa = 1e8, cap["sa_rwa"]
print(f"CET1 ratio today {t['start']:.1%}; requirement "
      f"{cap['requirement']:.1%}; minimum {cap['minimum']:.1%}")
print(f"\n{'scenario':<13}{'trough':>8}{'depletion':>11}{'$m':>8}"
      f"{'start needed':>14}")
for k in ("base", "severe", "stress_2026"):
    d = t["drop"][k]
    print(f"{k:<13}{s['trough_sa'][k]:>8.1%}{d:>11.1%}"
          f"{d * rwa / m:>8,.0f}{t['need'][k]:>14.1%}")
print(f"\ntarget: {cap['requirement']:.1%} + severe "
      f"{t['drop']['severe']:.1%} + buffer {ap.BUFFER:.1%} = "
      f"{t['target']:.1%}")
print(f"tolerance: minimum {cap['minimum']:.1%} + severe "
      f"{t['drop']['severe']:.1%} = {t['tolerance']:.1%}")
over = cap["cet1"] - t["target"] * rwa
print(f"CET1 above the target ${over / m:,.1f}m; above the "
      "requirement "
      f"${(cap['cet1'] - cap['requirement'] * rwa) / m:,.1f}m")
short = t["need"]["stress_2026"] * rwa - cap["cet1"]
print(f"to come through the supervisor's scenario at "
      f"{cap['requirement']:.1%}: ${short / m:,.1f}m more")

lo = pf.load()
ceiling = ap.ec_ceiling(cap)
print(f"\neconomic capital ${lo['ec_999'] / m:,.1f}m = "
      f"{lo['ec_999'] / cap['cet1']:.1%} of CET1")
print(f"most that leaves the {cap['minimum']:.1%} minimum after a "
      f"1-in-1,000 year: {ceiling:.1%}")
print(f"  (${ceiling * cap['cet1'] / m:,.1f}m; CET1 less "
      f"{cap['minimum']:.1%} of RWA)")

Path(__file__).with_suffix(".json").write_text(json.dumps({
    "now": t["start"], "req": cap["requirement"],
    "min": cap["minimum"], "target": t["target"],
    "tolerance": t["tolerance"], "troughs": s["trough_sa"],
    "need": t["need"]}, indent=1))
