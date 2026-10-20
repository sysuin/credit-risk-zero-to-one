# Commercial clients by grade: their share of the exposure and of the
# bad years, the margin they pay and the margin their risk needs.
import json
from pathlib import Path

import fernhill
from ballast import appetite as ap

con = fernhill.connect()
t = ap.returns(con, by="grade")
g = ap.margins(con, t)
g = g.loc[sorted(g.index, key=lambda s: int(s.split()[1]))]
c = ap.allocate(ap.pf.load_contributions(), ap.pf.load()["ec_999"])
c = c[c.kind == "name"].assign(grade=lambda d: d.id.map(ap.grades()))
by = c.groupby("grade")[["ead", "el", "es_999"]].sum()
by = by / by.sum()
print(f"{'grade':<7}{'drawn':>7}{'EAD':>6}{'EL':>6}{'ES':>6}"
      f"{'margin':>8}{'needed':>8}{'gap':>7}")
for name, r in g.iterrows():
    k = int(name.split()[1])
    print(f"{k:<7}{r.drawn / 1e8:>7,.0f}{by.ead[k]:>6.0%}"
          f"{by.el[k]:>6.0%}{by.es_999[k]:>6.0%}{r.now_bps:>8,.0f}"
          f"{r.need_bps:>8,.0f}{r.gap_bps:>+7,.0f}")
print("drawn $m; shares of the commercial book's EAD, expected loss")
print("and expected shortfall; margins in basis points over the")
print(f"policy rate; needed = a {ap.HURDLE:.0%} return on capital "
      "before running costs")
for b, (lo, hi) in ap.BANDS.items():
    s = by.loc[lo:hi].sum()
    print(f"  {b:<12} EAD {s.ead:.1%}, EL {s.el:.1%}, ES "
          f"{s.es_999:.1%}")

Path(__file__).with_suffix(".json").write_text(json.dumps({
    "grade": [int(k) for k in by.index], "ead": list(by.ead),
    "es": list(by.es_999),
    "now": [g.loc[f"grade {k}", "now_bps"] for k in by.index],
    "need": [g.loc[f"grade {k}", "need_bps"] for k in by.index]},
    indent=1))
