# Pluto and Tasche's most prudent PDs for the commercial grades: the
# highest PD each grade's record cannot rule out.
import json
from pathlib import Path

import fernhill
from ballast.commercial import rating as rt
from ballast.config import SEED
from ballast.parameters import pd as pdm

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv.window_complete]
g = dev.groupby("grade").default_12m.agg(["size", "sum"])
n, d = g["size"].to_numpy(), g["sum"].to_numpy()
book50 = pdm.pluto_tasche(n, d, 0.5)
book90 = pdm.pluto_tasche(n, d, 0.9)
top90 = pdm.pluto_tasche(n[:6], d[:6], 0.9)
corr90 = pdm.pluto_tasche(n[:6], d[:6], 0.9, rho=0.12, years=8,
                          sims=2000, seed=SEED)
print(f"{len(dev):,} reviews with a year after them, "
      f"{d.sum()} defaults")
print(f"{'':<16}{'whole book':>16}{'grades 1-6 only':>24}")
print(f"{'grade':<6}{'n':>5}{'d':>4}{'scale':>7}{'50%':>8}{'90%':>8}"
      f"{'90%':>9}{'90%, rho':>10}")
for i, grade in enumerate(g.index):
    tail = (f"{top90[i]:>9.2%}{corr90[i]:>10.2%}" if i < 6 else "")
    print(f"{grade:<6}{n[i]:>5}{d[i]:>4}{rt.pd_of(grade):>7.2%}"
          f"{book50[i]:>8.2%}{book90[i]:>8.2%}{tail}")
print(f"\nGrades 1-6: {n[:6].sum():,} reviews, {d[:6].sum()} defaults;"
      " rho 0.12 over 8 review years")
Path(__file__).with_suffix(".json").write_text(json.dumps({
    "n": n.tolist(), "d": d.tolist(), "book90": book90.tolist(),
    "top90": top90.tolist(), "corr90": corr90.tolist()}))
