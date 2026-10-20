# Checking against the answer: each applicant's true chance of going
# bad, from the truth database, for those who took the loan and those
# who walked away at the same price. Nothing in Ballast reads it.
import sys

import fernhill
from ballast.config import ROOT
from ballast.scorecard import points

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import scored  # noqa: E402

con = fernhill.connect()
truth = fernhill.connect(truth=True)
true_pd = truth.execute("SELECT app_id, pd12_at_open FROM origination "
                        "ORDER BY app_id").df()
a = scored(con).merge(true_pd, on="app_id")
ap = a[a["decision"].eq("approve") & a["override"].isna()].copy()
ap["took"] = ap["outcome"].eq("booked")
ap["promise"] = points.bad_rate_at(ap["m2r"])


def line(name, g):
    t, w = g[g["took"]], g[~g["took"]]
    print(f"  {name:<20}{len(t):>6,}{t['pd12_at_open'].mean():>8.2%}"
          f"{len(w):>7,}{w['pd12_at_open'].mean():>8.2%}"
          f"{g['promise'].mean():>9.2%}")


head = (f"  {'':<20}{'took':>6}{'true':>8}{'walked':>7}{'true':>8}"
        f"{'promised':>9}")
flat = ap[ap["app_date"].between("2017-01-01", "2018-12-31")]
print("One price for all, 2017-2018, by Mark II-R")
print(head)
for lo, hi in ((540, 559), (560, 579), (580, 599), (600, 619)):
    line(f"{lo}-{hi}", flat[flat["m2r"].between(lo, hi)])

when = (ap["app_date"].between("2019-04-01", "2024-12-31")
        & ~ap["app_date"].between("2020-04-01", "2021-01-31")
        & ap["price_test_arm"].isna())
edge = ap[when]
print("\nEither side of Mark I 600")
print(head)
line("580-599 (dear)", edge[edge["mark1_score"].between(580, 599)])
line("600-619 (cheaper)", edge[edge["mark1_score"].between(600, 619)])

test = ap[ap["app_date"].dt.year.eq(2024)].copy()
test["arm"] = test["price_test_arm"].fillna("policy")
print("\nThe 2024 price test")
print(head)
for arm in ("minus_150", "policy", "plus_150"):
    line(arm, test[test["arm"] == arm])
all_pd = test.groupby("arm")["pd12_at_open"].mean()
print("  everyone offered: " + ", ".join(
    f"{k} {all_pd[k]:.2%}" for k in ("minus_150", "policy",
                                     "plus_150")))
