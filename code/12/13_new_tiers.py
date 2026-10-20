# Fernhill's price tiers redrawn on Mark II-R's scale: where the
# edges go, what each tier must charge, and what its people pay today.
import sys

import pandas as pd

import fernhill
from ballast import pricing
from ballast.config import ROOT
from ballast.decision import policy as pol

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, mark1_tier, market, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
costs, m = pricing.Costs(lgd=lgd), market(con)
print(f"Book default rate halves every {-0.6931 / fd.b:.1f} points")

dec = pd.read_parquet(pol.DECISION / "decisions_2025.parquet")
yes = dec[dec["decision"].isin(["approve", "refer"])]
b = yes[["app_id"]].merge(a, on="app_id")
dec25 = a[a["decision"].eq("approve") & a["price_test_arm"].isna()
          & a["app_date"].between("2025-12-01", "2025-12-31")]
today = dec25.groupby(mark1_tier(dec25["mark1_score"]).array,
                      observed=True)["offered_rate_pct"].median()
b["today"] = mark1_tier(b["mark1_score"]).map(today).astype(float)\
    .to_numpy()
grid = pricing.Grid(edges=(565, 580, 595, 610), rates=(0,) * 5,
                    at_ftp_pct=0)
b["tier"] = grid.tier(b["m2r"])
names = grid.labels(550, 652)
print(f"\nBallast's approvals and referrals of 2025: {len(b):,}")
print(f"{'Mark II-R':<10}{'share':>6}{'PD at':>7}{'floor at':>9}"
      f"{'PD avg':>7}{'floor':>7}{'today':>7}{'range today':>13}")
for k, g in b.groupby("tier"):
    lo = 550 if k == 0 else grid.edges[k - 1]
    avg = float(fd.annual(g["m2r"]).mean())
    f_lo = pricing.floor_rate(1_200_000, 36, float(fd.annual(lo)),
                              float(fp.annual(lo)), m, costs)
    f_avg = pricing.floor_rate(1_200_000, 36, avg,
                               float(fp.annual(g["m2r"]).mean()), m,
                               costs)
    q = g["today"].quantile([0.1, 0.9]).to_numpy()
    print(f"{names[k]:<10}{len(g) / len(b):>6.0%}"
          f"{float(fd.annual(lo)):>7.1%}{f_lo:>9.2f}{avg:>7.1%}"
          f"{f_avg:>7.2f}{g['today'].mean():>7.2f}"
          f"{q[0]:>7.1f} to {q[1]:.1f}")
print("(floor: the rate that earns the hurdle on a $12,000, 36-month"
      "\n loan, at the tier's lowest score and at its average risk;"
      "\n today: Fernhill's December 2025 Mark I price for the same"
      "\n applicants)")
