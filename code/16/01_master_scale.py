# Fernhill's master scale: a PD for every grade, the band of PDs each
# grade covers, and where Fernhill's clients sat at the 2025 review.
import json

import fernhill
from ballast.commercial import rating as rt
from ballast.config import ROOT

con = fernhill.connect()
rv = rt.reviews(con)
latest = rv[rv.review_date == rv.review_date.max()]
counts = latest.grade.value_counts()
edges = [0.0, *rt.band_edges(), 1.0]
print(f"master scale; clients at the review of "
      f"{latest.review_date.max():%d %B %Y}")
print(f"{'grade':<7}{'PD':>8}{'band from':>12}{'to':>9}"
      f"{'clients':>10}{'share':>8}{'ratio':>7}")
for i, g in enumerate(rt.GRADES):
    p, n = rt.pd_of(g), counts.get(g, 0)
    ratio = (f"{p / rt.pd_of(g - 1):>7.1f}" if g > 1
             else f"{'':>7}")
    print(f"{g:<7}{p:>8.2%}{edges[i]:>12.3%}{edges[i + 1]:>9.3%}"
          f"{n:>10}{n / len(latest):>8.0%}"
          f"{ratio}")
print(f"{rt.DEFAULT:<7}{rt.pd_of(rt.DEFAULT):>8.0%}"
      f"{'in default':>21}")
print(f"\nclients reviewed: {len(latest)}; median grade "
      f"{latest.grade.median():.0f}")
avg = sum(rt.pd_of(g) * n for g, n in counts.items()) / len(latest)
print(f"average PD on the scale: {avg:.2%}")

out = ROOT / "code" / "16" / "01_master_scale.json"
out.write_text(json.dumps({
    "pd": [rt.pd_of(g) for g in rt.GRADES],
    "clients": [int(counts.get(g, 0)) for g in rt.GRADES]}))
