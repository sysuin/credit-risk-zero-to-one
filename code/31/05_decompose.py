# Each year's personal-loan charge-offs split into the book, the
# economy, cohort quality and chance, and the two changes Chapter 1
# argued about, with intervals from the model's own uncertainty.
import json

import numpy as np

import fernhill
from _chargeoffs import (PARTS, account_months, by_year, cells,
                         components, draws, fit, long_run_u,
                         unemployment)
from ballast.config import ROOT, SEED

con = fernhill.connect()
lr = long_run_u(con)
c = cells(account_months(con), unemployment(con))
res = fit(c, lr)
t = by_year(components(c, res.params, lr)).loc[2021:2025]
years = list(t.index)

# Whole dollars; chance takes the rounding so each column adds up.
r = t[["book", "economy", "quality", "push"]].round()
r["chance"] = t["actual"] - r[["book", "economy",
                                "quality"]].sum(axis=1)
sd = np.sqrt(res.scale * t["fitted"])
print(f"{'$':<13}" + "".join(f"{y:>11}" for y in years))
for label, col in [("charged off", None), (" book", "book"),
                   (" economy", "economy"), (" quality", "quality"),
                   ("  the push", "push"), (" chance", "chance")]:
    v = t["actual"] if col is None else r[col]
    signed = col not in (None, "book")
    print(f"{label:<13}" + "".join(f"{x:>+11,.0f}" if signed else
                                   f"{x:>11,.0f}" for x in v))
print(f"{'expected':<13}"
      + "".join(f"{x:>11,.0f}" for x in t["fitted"]))
print(f"{'chance, sd':<13}"
      + "".join(f"{x:>+11.1f}" for x in r["chance"] / sd))
print(f"one sd of chance in a year: about ${sd.mean():,.0f}")

# the same split again for 2,000 draws of the model's coefficients
rng = np.random.default_rng(SEED)
sims = []
for _, coefs in draws(res, 2000, rng).iterrows():
    sims.append(by_year(components(c, coefs, lr)))


def change(start, end):
    """Each part's change between two years, and its 90% interval
    across the 2,000 draws."""
    moved, interval = {}, {}
    for part in PARTS + ["push"]:
        moved[part] = t.loc[end, part] - t.loc[start, part]
        sims_moved = [x.loc[end, part] - x.loc[start, part]
                      for x in sims]
        interval[part] = np.percentile(sims_moved, [5, 95])
    return moved, interval


print(f"\n{'change, $000':<13}{'2023 to 2024':>22}{'2024 to 2025':>22}")
d1, i1 = change(2023, 2024)
d2, i2 = change(2024, 2025)
tot = [t.loc[2024, "actual"] - t.loc[2023, "actual"],
       t.loc[2025, "actual"] - t.loc[2024, "actual"]]
print(f"{'charged off':<13}{tot[0] / 1e3:>+8,.0f}{'':>14}"
      f"{tot[1] / 1e3:>+8,.0f}")
for label, p in [(" book", "book"), (" economy", "economy"),
                 (" quality", "quality"), ("  the push", "push"),
                 (" chance", "chance")]:
    cells_ = ""
    for d, i in ((d1, i1), (d2, i2)):
        cells_ += (f"{d[p] / 1e3:>+8,.0f}  {i[p][0] / 1e3:>+5,.0f} to"
                   f" {i[p][1] / 1e3:>+4,.0f}")
    print(f"{label:<13}{cells_}")
print("intervals: 90% of 2,000 draws of the model's coefficients")

(ROOT / "code/31/05_decompose.json").write_text(json.dumps(
    {"years": years,
     "parts": {p: [float(t.loc[y, p]) for y in years]
               for p in ["actual", "fitted", "push"] + PARTS},
     "sd": [float(x) for x in sd],
     "change": {k: {p: [float(d[p]), *map(float, i[p])]
                    for p in PARTS + ["push"]}
                for k, (d, i) in {"2024": (d1, i1),
                                  "2025": (d2, i2)}.items()}}) + "\n")
