# Does each grade default at the rate the master scale promises?
# Every review with a complete year after it, by the analysts' grade.
import json

import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt
from ballast.config import ROOT

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete")
t = mg.default_rates(dev, "grade")
print(f"{'grade':<5}{'reviews':>8}{'promised':>9}{'expected':>9}"
      f"{'defaults':>9}{'observed':>9}{'95% interval':>13}{'p':>5}")
for g, r in t.iterrows():
    print(f"{g:<5}{r.n:>8.0f}{r.promised:>9.2%}{r.expected:>9.1f}"
          f"{r.defaults:>9.0f}{r.observed:>9.2%}"
          f"{r.lower:>6.1%}-{r.upper:<6.1%}{r.p_value:>5.2f}")
print(f"{'all':<5}{t.n.sum():>8,.0f}{'':>9}{t.expected.sum():>9.1f}"
      f"{t.defaults.sum():>9.0f}")
for lo, hi in ((1, 6), (7, 10)):
    s = t.loc[lo:hi]
    print(f"grades {lo}-{hi}: expected {s.expected.sum():.1f}, "
          f"observed {s.defaults.sum():.0f}")
inside = ((t.promised >= t.lower) & (t.promised <= t.upper)).sum()
print(f"promised PD inside the interval: {inside} of {len(t)} grades")

out = ROOT / "code" / "16" / "11_default_rates.json"
out.write_text(json.dumps({k: t[k].tolist() for k in (
    "n", "defaults", "observed", "promised", "lower", "upper")}))
