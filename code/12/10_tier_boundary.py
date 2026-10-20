# Either side of Mark I 600, where the price jumps by five points and
# the applicants barely differ: who took the loan, and how they paid.
import sys

from scipy.stats import chi2

import fernhill
from ballast.config import ROOT
from ballast.scorecard import points, sample

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
a = a.merge(sample.load_sample()[["app_id", "outcome"]], on="app_id",
            how="left", suffixes=("", "_12m"))
retro = con.execute("SELECT * FROM bureau_retro ORDER BY app_id").df()
a = a.merge(retro, on="app_id", how="left")
when = (a["app_date"].between("2019-04-01", "2024-12-31")
        & ~a["app_date"].between("2020-04-01", "2021-01-31"))
ap = a[when & a["decision"].eq("approve") & a["override"].isna()
       & a["price_test_arm"].isna()
       & a["mark1_score"].between(570, 629)].copy()
ap["took"] = ap["outcome"].eq("booked")
ap["promise"] = points.bad_rate_at(ap["m2r"])
ap["bin"] = (ap["mark1_score"] // 10 * 10).astype(int)
known = ap["took"] & ap["outcome_12m"].isin(["good", "bad"])
ap["bad"] = ap["outcome_12m"].eq("bad")
print(f"{'Mark I':<9}{'price':>6}{'took':>6}{'MkII-R':>7}{'loans':>6}"
      f"{'bad':>6}{'promised':>9}{'ratio':>6}")
for b, g in ap.groupby("bin"):
    k = g[known[g.index]]
    print(f"{b}-{b + 9:<5}{g['offered_rate_pct'].mean():>6.1f}"
          f"{g['took'].mean():>6.0%}{g['m2r'].mean():>7.1f}{len(k):>6,}"
          f"{k['bad'].mean():>6.1%}{k['promise'].mean():>9.1%}"
          f"{k['bad'].mean() / k['promise'].mean():>6.2f}")


def ratio(g):
    """Bads seen over bads promised, with an exact 95% interval."""
    n, e = int(g["bad"].sum()), g["promise"].sum()
    lo = chi2.ppf(0.025, 2 * n) / 2 / e
    hi = chi2.ppf(0.975, 2 * n + 2) / 2 / e
    return n, e, n / e, lo, hi


print("\nBooked loans, seen against promised")
for name, m in (("580-599 (dear)", ap["bin"].isin([580, 590])),
                ("600-619 (cheaper)", ap["bin"].isin([600, 610]))):
    n, e, r, lo, hi = ratio(ap[m & known])
    print(f"  {name:<18} {n:>3} bads, {e:5.1f} promised: "
          f"{r:.2f} ({lo:.2f} to {hi:.2f})")

print("\nWho walked away, as the bureau saw them later (to 2023)")
for name, m in (("580-599", ap["bin"].isin([580, 590])),
                ("600-619", ap["bin"].isin([600, 610]))):
    w = ap[m & ~ap["took"] & ap["opened_elsewhere"].notna()]
    e = w[w["opened_elsewhere"].astype(bool)]
    bad = e["bad_12m_elsewhere"].astype(float).mean()
    print(f"  {name}: {len(w):,} walked; {len(e) / len(w):.0%} borrowed"
          f" elsewhere,\n    and {bad:.1%} of those loans went bad")
