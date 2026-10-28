# Mark I scored on the bureau's version 3 against Mark I scored on the
# ruler its bureau points were drawn on: what the same cut-off approved.
import json

import numpy as np
import pandas as pd

from ballast import data
from ballast.config import ROOT
from ballast.decision import engine
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")].copy()
v2_to_v3 = engine.bureau_map()
edges, _ = pol.MARK1["bureau_score"]
on_v3 = [int(v2_to_v3[e]) for e in edges]
print("Mark I's bureau bands: where each edge sits on version 3")
print("  v2 edge  " + "".join(f"{e:>6}" for e in edges))
print("  v3 edge  " + "".join(f"{e:>6}" for e in on_v3))

v3 = p["bureau_version"].astype(str).eq("v3").to_numpy()
p["rescored"] = np.where(v3, pol.mark1_score(p, bureau_edges=on_v3),
                         p["mark1_score"])
gain = (p["mark1_score"] - p["rescored"])[v3 & p["bureau_hit"]]
print("\nPoints Mark I gained on version 3 (applicants with a file)")
print(f"  mean {gain.mean():.1f}, median {gain.median():.0f}, "
      f"none {(gain == 0).mean():.1%}, "
      f"30 or more {(gain >= 30).mean():.1%}")

limits = [pol.period_of(d)[2] for d in p["app_date"]]
rule = pol.policy_reason(p, limits)
p = p[rule.isna().to_numpy()
      & ~p["decline_reason"].astype(object).eq("fraud_check")]
p["day"] = pd.to_datetime(p["app_date"].astype("datetime64[s]"))
PERIODS = [("Jan-Jun 2019", "2019-01-01", "2019-06-30"),
           ("Jul 2019-Mar 2020", "2019-07-01", "2020-03-31"),
           ("Apr 2020-Jan 2021", "2020-04-01", "2021-01-31"),
           ("Feb 2021-Jun 2022", "2021-02-01", "2022-06-30"),
           ("Jul 2022-Dec 2025", "2022-07-01", "2025-12-31")]
print("\nPersonal applicants past the rules: share above the band")
print(f"  {'applied':<19}{'cut':>4}{'v3':>7}{'v2 ruler':>9}"
      f"{'approved':>9}{'crept':>6}{'as if':>6}")
for name, lo, hi in PERIODS:
    g = p[(p["day"] >= lo) & (p["day"] <= hi)]
    cut = int(g["cutoff"].iloc[0])
    above = (g["mark1_score"] >= cut + pol.REFER).mean()
    fixed = (g["rescored"] >= cut + pol.REFER).mean()
    ok = g["decision"].astype(str).eq("approve")
    crept = int((ok & (g["rescored"] < cut - pol.REFER)
                 & (g["mark1_score"] >= cut - pol.REFER)).sum())
    # The cut-off on the old ruler that passes as many as `cut` did:
    # try every score and keep the first whose pass rate is closest.
    share = (g["mark1_score"] >= cut).mean()
    as_if, best = None, 2.0
    for c in range(400, 700):
        gap = abs((g["rescored"] >= c).mean() - share)
        if gap < best:
            as_if, best = c, gap
    print(f"  {name:<19}{cut:>4}{above:>7.1%}{fixed:>9.1%}"
          f"{ok.mean():>9.1%}{crept:>6,}{as_if:>6}")

# For the figure: the share above the band, month by month.
m = p[p["day"] >= "2018-01-01"].copy()
m["month"] = m["day"].dt.to_period("M").astype(str)
m["above"] = m["mark1_score"] >= m["cutoff"] + pol.REFER
m["above_v2"] = m["rescored"] >= m["cutoff"] + pol.REFER
monthly = m.groupby("month").agg(above=("above", "mean"),
                                 above_v2=("above_v2", "mean"),
                                 cutoff=("cutoff", "first"))
rows = []
for month, r in monthly.iterrows():
    row = {"month": month}
    for col, v in r.items():
        row[col] = round(float(v), 4)
    rows.append(row)
path = ROOT / "code" / "11" / "02_the_ruler.json"
path.write_text(json.dumps(rows, indent=1) + "\n")
