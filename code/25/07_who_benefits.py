# Does phoning first help some accounts more than others? The test's
# effect on next-month cures, split five ways, each split tested.
import json

import numpy as np
import pandas as pd

import fernhill
from ballast import collections as coll
from ballast.config import ROOT

con = fernhill.connect()
t = coll.test_accounts(con)
hist = coll.entries(con, "2016-01-01", "2023-12-31")
model = coll.fit(hist, "cured_3m")
cons = t["family"].eq("consumer")
t["predicted"] = np.where(cons, "", "business")
t.loc[cons, "predicted"] = pd.cut(
    coll.predict(model, t[cons]), [0, 0.60, 0.75, 1],
    labels=["likely to roll", "in between", "likely to cure"]
).astype(str)
t["kind"] = np.where(cons, t["product"], "business")
t["history"] = np.where(t["repeat"].eq(1), "behind before",
                        "first time")
t["size"] = np.where(t["balance"] >= t["balance"].median(),
                     "above median", "below median")
splits = {"family": "family", "product": "kind",
          "predicted cure": "predicted", "past arrears": "history",
          "balance": "size"}
rows, n_groups = [], 0
print(f"{'':<22}{'n':>6}{'call':>7}{'text':>7}{'difference (95%)':>22}")
for title, col in splits.items():
    p = coll.interaction_p(t, "cured_1m", col)
    print(f"{title} (does it differ? p = {p:.2f})")
    for g, s in t.groupby(col):
        a, b = s.loc[s["call"] == 1, "cured_1m"], s.loc[
            s["call"] == 0, "cured_1m"]
        d, lo, hi = coll.diff_in_proportions(a.sum(), len(a), b.sum(),
                                             len(b))
        n_groups += 1
        rows.append({"split": title, "group": g, "d": d, "lo": lo,
                     "hi": hi, "n": len(s)})
        flag = " *" if lo > 0 or hi < 0 else ""
        print(f"  {g:<20}{len(s):>6,}{a.mean():>7.1%}{b.mean():>7.1%}"
              f"{100 * d:>+8.1f} ({100 * lo:+.1f} to {100 * hi:+.1f})"
              f"{flag}")
print(f"* interval excludes zero; {n_groups} groups in {len(splits)} "
      f"splits")
print(f"Bonferroni for {len(splits)} splits: p below "
      f"{0.05 / len(splits):.3f} to count")
json.dump(rows, open(ROOT / "code/25/07_who_benefits.json", "w"),
          indent=1, default=float)
