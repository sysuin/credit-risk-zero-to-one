# Stability: has the population Mark II-R scores moved away from the
# one it was built on? PSI of the score by year against development,
# and of each line's points in 2025.
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fernhill
from ballast import data
from ballast import validation as vd
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import reject

card = engine.load_champion(pol.load_policy())
a = reject.applicants()
a = a[~a["policy"]].copy()
a["date"] = pd.to_datetime(a["app_date"].astype("datetime64[s]"))
dev = a[a["date"].dt.year <= 2022]
dev_lines = card.line_points(dev)
dev_score = card.base + dev_lines.sum(axis=1)
EDGES = np.unique(np.quantile(dev_score, np.arange(0.1, 1.0, 0.1)))

raw = data.load_applications(fernhill.connect(), unknowns=False)
new = raw[raw["product"].astype(str).eq("personal")
          & (raw["app_date"].astype(str) >= "2025-01-01")]
dec = engine.decide_all(new, pol.load_policy(), card)
new = new[(dec["stage"] == "score").to_numpy()]
quarter = pd.to_datetime(new["app_date"].astype("datetime64[s]")
                         ).dt.to_period("Q").to_numpy()
new = engine.prepare(new)
new_lines = card.line_points(new)
new_score = card.base + new_lines.sum(axis=1)

print(f"Reference: {len(dev):,} applicants past the rules, 2016-2022;"
      f"\nmean score {dev_score.mean():.1f}, cut into "
      f"{len(EDGES) + 1} bands at its deciles")
print(f"{'applied':<10}{'applicants':>11}{'mean':>8}{'PSI':>8}"
      "  reading")
series = []
for q, g in a[a["date"].dt.year >= 2017].groupby(
        a["date"].dt.to_period("Q")):
    series.append({"q": str(q), "psi": round(vd.psi(
        dev_score, card.score(g), EDGES), 4)})
for yr in range(2019, 2025):
    s = card.score(a[a["date"].dt.year == yr])
    v = vd.psi(dev_score, s, EDGES)
    print(f"{yr:<10}{len(s):>11,}{s.mean():>8.1f}{v:>8.3f}  "
          f"{vd.psi_reading(v)}")
v = vd.psi(dev_score, new_score, EDGES)
print(f"{'2025':<10}{len(new_score):>11,}{new_score.mean():>8.1f}"
      f"{v:>8.3f}  {vd.psi_reading(v)}")
for q, g in new_score.groupby(quarter):
    series.append({"q": str(q), "psi": round(vd.psi(
        dev_score, g, EDGES), 4)})

print("\n2025 against 2016-2022, line by line (points per line)")
print(f"{'line':<24}{'mean then':>10}{'mean 2025':>10}{'PSI':>8}")
for c in card.characteristics:
    edges = np.unique(dev_lines[c])[1:]
    print(f"{c:<24}{dev_lines[c].mean():>10.1f}"
          f"{new_lines[c].mean():>10.1f}"
          f"{vd.psi(dev_lines[c], new_lines[c], edges):>8.3f}")
Path(__file__).with_suffix(".json").write_text(
    json.dumps(series) + "\n")
