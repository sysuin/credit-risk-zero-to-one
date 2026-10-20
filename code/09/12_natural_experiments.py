# Two times Fernhill lent below its own line, and what they show.
import datetime as dt

import fernhill
from _truth import applicants_with_truth
from ballast.scorecard import points

a = applicants_with_truth()
a["mark2"] = points.load_scorecard().score(a)
a["promise"] = points.bad_rate_at(a["mark2"])
z = fernhill.connect(truth=True).execute(
    "SELECT app_id, z FROM applicants ORDER BY app_id").df()
a = a.merge(z, on="app_id", how="left", validate="1:1")
dev = a[a["period"] == "development"]


def line(name, g, y="truth"):
    print(f"{name:<26}{len(g):>6,}{g[y].mean():>8.1%}"
          f"{g['promise'].mean():>9.1%}{g['z'].mean():>7.2f}")


hdr = f"{'':<26}{'n':>6}{'bad':>8}{'Mark II':>9}{'z':>7}"
print("1. low-side overrides, branch, below the refer band")
print(hdr)
branch = dev[dev["channel"].eq("branch") & (dev["margin"] < -10)
             & ~dev["policy"]]
ov = branch[branch["override"].eq("low_side")]
line("overrides, booked", ov[ov["known"] & ov["bad"].notna()], "bad")
line("overrides, all (truth)", ov)
line("other branch declines", branch[branch["override"].isna()])
print()
print("2. the growth push: Mark I below 560 (every other cut-off)")
print(hdr)
low = dev[(dev["mark1_score"] >= 525) & (dev["mark1_score"] < 560)
          & ~dev["policy"]]
push = ((low["app_date"] >= dt.date(2021, 2, 1))
        & (low["app_date"] < dt.date(2022, 7, 1)))
p = low[push]
bk = p[p["known"] & p["bad"].notna()]
line("push, booked", bk, "bad")
line("push, booked (truth)", p[p["known"]])
line("push, walked away (truth)", p[p["outcome"].eq("not_taken_up")])
line("other years, declined",
     low[~push & low["outcome"].eq("declined")])
print()
print("bad: observed for booked loans, true otherwise; z: latent "
      "quality")
