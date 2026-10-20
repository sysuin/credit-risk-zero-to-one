# At a random price, who took the loan? The test's takers in each arm,
# by what Fernhill knew at application and how they have paid since.
import sys

import fernhill
from ballast.config import ROOT
from ballast.decision import strategy
from ballast.scorecard import points

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
t = a[a["decision"].eq("approve") & a["app_date"].dt.year.eq(2024)
      & a["outcome"].eq("booked")].copy()
t["arm"] = t["price_test_arm"].fillna("policy")
t["promise"] = points.bad_rate_at(t["m2r"])
late = con.execute("""
    SELECT a.app_id, max(p.missed) AS worst, ap.worst_status_24m AS ws
    FROM accounts a JOIN performance p USING (account_id)
    JOIN applications ap ON ap.app_id = a.app_id
    WHERE a.product = 'personal' AND year(a.open_date) >= 2024
    GROUP BY a.app_id, ap.worst_status_24m ORDER BY 1""").df()
t = t.merge(late, on="app_id")
order = ["minus_150", "policy", "plus_150"]
arms = {k: t[t["arm"] == k] for k in order}
rows = {
    "loans": lambda g: f"{len(g):,}",
    "Mark II-R": lambda g: f"{g['m2r'].mean():.1f}",
    "promised bad": lambda g: f"{g['promise'].mean():.2%}",
    "late 30+ on file": lambda g: f"{(g['ws'] >= 30).mean():.1%}",
    "via broker": lambda g: f"{g['channel'].eq('broker').mean():.1%}",
    "missed 1+ by Dec": lambda g: f"{(g['worst'] >= 1).mean():.1%}",
    "missed 3+ by Dec": lambda g: f"{(g['worst'] >= 3).mean():.1%}",
    "  (count)": lambda g: f"{(g['worst'] >= 3).sum()}",
}
print("Loans booked from 2024's approvals, by the price quoted")
print(f"{'':<18}" + "".join(f"{k:>11}" for k in order))
for name, f in rows.items():
    print(f"{name:<18}" + "".join(f"{f(arms[k]):>11}" for k in order))

p = (arms["policy"]["worst"] >= 3).mean()
print(f"\nTo tell {p:.1%} from a fifth more, {1.2 * p:.1%}, needs "
      f"{strategy.n_per_arm(p, 1.2 * p):,} loans an arm;")
print(f"from twice as many, {2 * p:.1%}: "
      f"{strategy.n_per_arm(p, 2 * p):,} an arm.")
