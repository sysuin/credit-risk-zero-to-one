# The loans Fernhill made only because the ruler moved: how they paid,
# what they did to the 2019 vintage, and to Mark I's Gini.
import numpy as np
import pandas as pd

import fernhill
from ballast import data
from ballast import performance as perf
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import metrics, sample

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")
        & raw["decision"].astype(str).eq("approve")].copy()
p["v2_ruler"] = pol.mark1_on_v2_ruler(p, engine.bureau_map())
cut = p["cutoff"].astype(int)
# Crept: approved on version 3, below the refer band on the old ruler.
p["crept"] = ((p["v2_ruler"] < cut - pol.REFER)
              & (p["mark1_score"] >= cut - pol.REFER)
              & p["override"].isna())
out = sample.outcomes(con)
out = out.rename(columns={"outcome": "window"})
p = p.merge(out[["account_id", "bad", "window", "complete"]],
            on="account_id", how="left")
p["day"] = pd.to_datetime(p["app_date"].astype("datetime64[s]"))

p["booked"] = p["outcome"].astype(str).eq("booked")
print("Approvals that crept in, and the loans they became")
print(f"  {'applied':<19}{'crept':>6}{'took':>6}{'bad':>7}"
      f"{'others':>8}{'took':>6}{'bad':>7}")
for name, lo, hi in [("Jul 2019-Mar 2020", "2019-07-01", "2020-03-31"),
                     ("Apr 2020-Jan 2021", "2020-04-01", "2021-01-31"),
                     ("Feb 2021-Jun 2022", "2021-02-01", "2022-06-30"),
                     ("Jul 2022-Jun 2024", "2022-07-01", "2024-06-30")]:
    g = p[(p["day"] >= lo) & (p["day"] <= hi)]
    done = g["complete"].fillna(False).astype(bool) & g["window"].isin(
        ["good", "bad"])
    row = f"  {name:<19}"
    for m in (g["crept"], ~g["crept"]):
        row += (f"{int(m.sum()):>{6 if row.endswith(' ') else 8},}"
                f"{g.loc[m, 'booked'].mean():>6.0%}"
                f"{g.loc[m & done, 'bad'].mean():>7.1%}")
    print(row)

eps = perf.default_episodes(con, "dod2021")
acc = perf.cohort_accounts(con, "personal", eps)
v19 = acc[acc["open_month"].dt.year == 2019].merge(
    p.loc[p["booked"], ["account_id", "crept"]], on="account_id",
    how="left")
v19["crept"] = v19["crept"].fillna(False).astype(bool)
print("took: share of approvals booked; bad: 3 missed in the first"
      " twelve\npayments, loans with a complete window")
print("\nThe 2019 vintage, in default by 24 months on book (dod2021)")
for name, g in [("all loans", v19),
                ("without the crept", v19[~v19["crept"]]),
                ("the crept alone", v19[v19["crept"]])]:
    rate = (g["default_mob"] <= 24).mean()
    print(f"  {name:<20}{len(g):>6,} loans {rate:>7.2%}")

s = sample.load_sample().merge(
    p.loc[p["booked"], ["app_id", "mark1_score", "v2_ruler"]],
    on="app_id")
s = s[s["outcome"].isin(["good", "bad"])]
print("\nMark I's Gini on Mark II's booked loans")
print(f"  {'sample':<14}{'as scored':>10}{'v2 ruler':>10}")
for split in ("holdout", "out_of_time"):
    g = s[s["split"] == split]
    g1 = metrics.gini(g["mark1_score"], g["bad"])
    g2 = metrics.gini(g["v2_ruler"], g["bad"])
    print(f"  {split:<14}{g1:>10.3f}{g2:>10.3f}")
oot = s[s["split"] == "out_of_time"]
moved = np.corrcoef(oot["mark1_score"], oot["v2_ruler"])[0, 1]
print(f"  out of time, correlation of the two: {moved:.3f}")
