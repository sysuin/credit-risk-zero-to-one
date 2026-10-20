# Early reads: what each half-year of personal loans showed at three
# and six months, against the 90+ rate it reached by twelve.
import json

import numpy as np

import fernhill
from ballast import monitoring as mon
from ballast.config import ROOT

con = fernhill.connect()
h = mon.early_reads(con, "personal", freq="H")
q = mon.early_reads(con, "personal")
print("Personal loans by half-year opened: share of loans that were")
print(f"{'opened':<8}{'loans':>7}{'30+ by':>9}{'60+ by':>9}"
      f"{'90+ by':>9}{'90+ by':>9}")
print(f"{'':<8}{'':>7}{'month 3':>9}{'month 6':>9}{'month 12':>9}"
      f"{'month 24':>9}")


def cell(x):
    return f"{x:>9.2%}" if np.isfinite(x) else f"{'..':>9}"


for r in h[h["vintage"] >= "2017"].itertuples():
    print(f"{r.vintage:<8}{r.loans:>7,}{cell(r.e3)}{cell(r.e6_60)}"
          f"{cell(r.b12)}{cell(r.b24)}")
done = q.dropna(subset=["b12"])
print(f"\nquarterly vintages with a 12-month read: {len(done)}")
for k in ("e3", "e6", "e6_60"):
    r = np.corrcoef(done[k], done["b12"])[0, 1]
    print(f"  correlation of {mon.READ_TEXT[k]:<15} with 90+ by month"
          f" 12: {r:.2f}")
fig = {"vintage": list(q["vintage"]),
       **{k: [None if not np.isfinite(x) else round(float(x), 5)
              for x in q[k]] for k in ("e3", "e6_60", "b12")}}
(ROOT / "code" / "24" / "05_early_reads.json").write_text(
    json.dumps(fig) + "\n")
