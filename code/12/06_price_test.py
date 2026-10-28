# The 2024 price test: one approved personal-loan applicant in ten was
# quoted 1.5 points above or below policy, at random. Who took it?
import json
import sys

import numpy as np

import fernhill
from ballast.config import ROOT, SEED

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
t = a[a["decision"].eq("approve") & a["app_date"].dt.year.eq(2024)
      ].copy()
t["arm"] = t["price_test_arm"].fillna("policy")
t["took"] = t["outcome"].eq("booked")
shift = {"minus_150": -1.5, "policy": 0.0, "plus_150": 1.5}
t["change"] = t["arm"].map(shift)
t["policy_rate"] = t["offered_rate_pct"] - t["change"]
order = ["minus_150", "policy", "plus_150"]


def column(g):
    """One arm's column of the table, as printed text."""
    return {
        "approved": f"{len(g):,}",
        "Mark I": f"{g['mark1_score'].mean():.1f}",
        "Mark II-R": f"{g['m2r'].mean():.1f}",
        "policy price": f"{g['policy_rate'].mean():.2f}%",
        "price quoted": f"{g['offered_rate_pct'].mean():.2f}%",
        "amount": f"${g['offered_amount_cents'].mean() / 100:,.0f}",
        "via broker": f"{g['channel'].eq('broker').mean():.1%}",
        "took the loan": f"{g['took'].mean():.1%}",
    }


arms = {k: t[t["arm"] == k] for k in order}
columns = [column(arms[k]) for k in order]
print(f"{'':<16}" + "".join(f"{k:>11}" for k in order))
for name in columns[0]:
    cells = "".join(f"{c[name]:>11}" for c in columns)
    print(f"{name:<16}" + cells)


def interval(g):
    p, n = g["took"].mean(), len(g)
    h = 1.96 * np.sqrt(p * (1 - p) / n)
    return p, p - h, p + h


lo, hi = arms["minus_150"]["took"], arms["plus_150"]["took"]
diff = hi.mean() - lo.mean()
se = np.sqrt(hi.var(ddof=0) / len(hi) + lo.var(ddof=0) / len(lo))
ci = [100 * (diff + k * 1.96 * se) for k in (-1, 1)]
print(f"\nTake-up, 3 points dearer: {100 * diff:+.1f} points "
      f"(95% interval\n  {ci[0]:+.1f} to {ci[1]:+.1f}); per point of "
      f"price {100 * diff / 3:+.1f}")
pr = {k: arms[k]["offered_rate_pct"].mean() for k in order}


def elasticity(up_lo, up_hi):
    """Per cent change in take-up per per cent change in price."""
    dear = np.log(pr["plus_150"] / pr["minus_150"])
    return np.log(up_hi / up_lo) / dear


rng = np.random.default_rng(SEED)
x, y = lo.to_numpy(), hi.to_numpy()
boot = [elasticity(rng.choice(x, len(x)).mean(),
                   rng.choice(y, len(y)).mean()) for _ in range(2000)]
e = elasticity(lo.mean(), hi.mean())
print(f"Price elasticity of take-up: {e:.2f} "
      f"(bootstrap 95%: {np.percentile(boot, 2.5):.2f} to "
      f"{np.percentile(boot, 97.5):.2f})")
(ROOT / "code" / "12" / "06_price_test.json").write_text(json.dumps(
    {k: dict(zip(["p", "lo", "hi"], map(float, interval(arms[k]))),
             n=len(arms[k]), price=float(pr[k])) for k in order},
    indent=1) + "\n")
