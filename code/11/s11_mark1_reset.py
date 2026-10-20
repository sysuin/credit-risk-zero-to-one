# Exercise 11.1: Mark I with its bureau bands moved to version 3, on
# the applicants of 2025, at the cut-off of 580.
import numpy as np

from ballast import data
from ballast.decision import engine
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")
        & (raw["app_date"].astype(str) >= "2025-01-01")]
p = p[pol.policy_reason(p).isna().to_numpy()]
fixed = pol.mark1_on_v2_ruler(p, engine.bureau_map())
old = p["mark1_score"]
print(f"{len(p):,} applicants of 2025 past the rules")
for name, s in (("Mark I as scored", old),
                ("Mark I, bands moved", fixed)):
    above = (s >= 590).mean()
    band = ((s >= 570) & (s < 590)).mean()
    print(f"  {name:<21} above the band {above:.1%}, in it {band:.1%}")
share = (old >= 580).mean()
cut = min(range(500, 650),
          key=lambda c: abs((fixed >= c).mean() - share))
print(f"Same approvals on the moved bands: cut-off {cut}")
card = engine.load_champion(pol.load_policy())
m2r = card.score(engine.prepare(p)).to_numpy()
fx = (fixed >= 580).to_numpy()
print(f"Moved Mark I at 580 and Mark II-R at 554 agree on "
      f"{np.mean(fx == (m2r >= 554)):.1%}")
