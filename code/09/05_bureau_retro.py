# What the bureau saw later of the applicants Fernhill did not lend to.
import numpy as np

import fernhill
from ballast.scorecard import points, reject

con = fernhill.connect()
lo, hi, n, pl = con.execute("""
    SELECT min(a.app_date), max(a.app_date), count(*),
           count(*) FILTER (WHERE a.product = 'personal')
    FROM bureau_retro r JOIN applications a USING (app_id)
    """).fetchone()
print(f"bureau_retro: {n:,} applications, {pl:,} of them personal")
print(f"applied from {lo} to {hi}")
a = reject.applicants()
a["mark2"] = points.load_scorecard().score(a)
r = reject.retro()
dev = a[(a["period"] == "development") & ~a["policy"]]
x = dev.merge(r, on="app_id", how="left")
x["covered"] = x["opened_elsewhere"].notna()
yr = x["app_date"].map(lambda d: d.year)
print()
print(f"{'2019-2022':<14}{'applicants':>11}{'in retro':>10}"
      f"{'opened':>8}{'bad there':>11}")
for out in ("declined", "not_taken_up"):
    g = x[(x["outcome"] == out) & (yr >= 2019)]
    op = g[g["opened_elsewhere"].eq(True)]
    print(f"{out:<14}{len(g):>11,}{g['covered'].mean():>10.1%}"
          f"{g['opened_elsewhere'].astype(float).mean():>8.1%}"
          f"{op['bad_elsewhere'].mean():>11.1%}")
print()
edges = [540, 560, 580, 600]
names = ["<540", "540-559", "560-579", "580-599", "600+"]
x["band"] = np.searchsorted(edges, x["mark2"], side="right")
d = x[(x["outcome"] == "declined") & x["covered"]]
b = x[x["known"] & x["bad"].notna() & (yr >= 2019)]
print(f"{'Mark II':<9}{'declined':>9}{'opened':>8}{'bad there':>11}"
      f"{'booked bad':>12}")
for k in range(len(names)):
    g, h = d[d["band"] == k], b[b["band"] == k]
    op = g[g["opened_elsewhere"].eq(True)]
    print(f"{names[k]:<9}{len(g):>9,}"
          f"{g['opened_elsewhere'].astype(float).mean():>8.1%}"
          f"{op['bad_elsewhere'].mean():>11.1%}"
          f"{h['bad'].mean():>12.1%}")
