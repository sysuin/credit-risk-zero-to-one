# The car loans Fernhill could sell on 31 December 2025: which are
# eligible, and what the pool would hold.
import numpy as np

import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
c = sec.candidates(con)
steps = [("car loans open on 31 Dec 2025", np.ones(len(c), bool)),
         ("  up to date", c.up_to_date.to_numpy()),
         ("  and at least one payment made", c.seasoned.to_numpy()),
         ("  and never in default", c.never_defaulted.to_numpy()),
         ("  and something still owed",
          (c.balance_cents > 0).to_numpy())]
keep = np.ones(len(c), bool)
print(f"{'':<34}{'loans':>7}{'balance $':>16}")
for label, flag in steps:
    keep &= flag
    cents = int(c.loc[keep, "balance_cents"].sum())
    print(f"{label:<34}{keep.sum():>7,}{cents / 100:>16,.0f}")

p = sec.pool(con)
p["band"] = p["band"].astype(str)
print(f"\n{'Mark I band':<12}{'loans':>7}{'balance $':>14}{'rate':>8}"
      f"{'months left':>13}{'LTV':>7}")
order = ["<600", "600-629", "630-659", "660+"]
for b, g in [(b, p[p.band == b]) for b in order] + [("all", p)]:
    gw = g["balance_cents"] / g["balance_cents"].sum()
    print(f"{b:<12}{len(g):>7,}"
          f"{int(g.balance_cents.sum()) / 100:>14,.0f}"
          f"{(gw * g.rate_pct).sum():>7.2f}%"
          f"{(gw * g.remaining).sum():>13.1f}"
          f"{(gw * g.ltv).sum():>7.0%}")
w = p["balance_cents"] / p["balance_cents"].sum()
big = p["balance_cents"].max() / 100
print(f"\nweighted age {(w * p.mob).sum():.1f} months; largest loan "
      f"${big:,.0f};\n{(w * (p.ltv >= 0.9)).sum():.1%} of the balance "
      f"at an indexed LTV of 90% or more")
