# Swap sets: at the approval rate Fernhill ran, whom each new scorecard
# approves that Mark I declined, and the reverse, with what was seen.
import json

import numpy as np
import pandas as pd

from ballast.config import ROOT
from ballast.decision import strategy
from ballast.scorecard import points, reject

a = reject.applicants()
a = a[~a["policy"]].merge(reject.retro(), on="app_id", how="left")
a["mark2"] = points.load_scorecard().score(a)
a["mark2r"] = reject.load_refit("mark2_retro_ws").scorecard().score(a)
elsewhere = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(elsewhere, a["bad_elsewhere"], np.nan))
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
SAMPLES = {
    "holdout 2019-22": (a["split"] == "holdout") & (year >= 2019),
    "2023": (a["split"] == "out_of_time") & (year == 2023)}
CELLS = {"only A approves": "swapped in", "only B approves":
         "swapped out", "both approve": "both approve"}
print("At Fernhill's approval rate, against Mark I's score alone")
print(f"{'':<25}{'people':>6}{'seen':>7}{'bad rate':>9}"
      f"{'promised':>10}")
saved = {}
for name, m in SAMPLES.items():
    d = a[m]
    share = d["outcome"].ne("declined").mean()
    mark1 = strategy.top_share(d["mark1_score"], share)
    print(f"{name} (approving {share:.1%})")
    for label, col in (("Mark II", "mark2"), ("Mark II-R", "mark2r")):
        new = strategy.top_share(d[col], share)
        t = strategy.swap_set(new, mark1, d["seen"],
                              points.bad_rate_at(d[col]))
        cells = list(CELLS) if col == "mark2r" else list(CELLS)[:2]
        for k, cell in enumerate(cells):
            r = t.loc[cell]
            print(f"  {label if k == 0 else '':<10}{CELLS[cell]:<13}"
                  f"{int(r['n']):>6,}{int(r['known']):>7,}"
                  f"{r['bad_rate']:>9.1%}"
                  f"{r['promised']:>10.1%}")
        if col == "mark2r":
            saved[name] = {"share": round(share, 4), **{
                c: {k: (round(float(v), 6) if k != "n" and k != "known"
                        else int(v)) for k, v in t.loc[c].items()}
                for c in t.index}}
print("seen: booked at Fernhill, or borrowed elsewhere (bureau retro)")
(ROOT / "code" / "11" / "08_swap_sets.json").write_text(
    json.dumps(saved, indent=1) + "\n")
