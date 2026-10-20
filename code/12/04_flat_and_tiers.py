# Who took Fernhill's loan under one flat price, 2017-2018, and under
# the tiers of April 2019 to March 2020: take-up and the book's mix.
import json
import sys

import fernhill
from ballast.config import ROOT
from ballast.scorecard import points

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import mark1_tier, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
ap = a[a["decision"].eq("approve") & a["override"].isna()].copy()
ap["took"] = ap["outcome"].eq("booked")
ap["tier"] = mark1_tier(ap["mark1_score"]).array
ap["promise"] = points.bad_rate_at(ap["m2r"])
periods = {"flat": ("2017-01-01", "2018-12-31"),
           "tiers": ("2019-04-01", "2020-03-31")}
out = {}
print(f"{'Mark I':<9}{'flat: price':>12}{'took':>6}{'mix':>6}"
      f"{'tiers: price':>14}{'took':>6}{'mix':>6}")
for name, (lo, hi) in periods.items():
    g = ap[ap["app_date"].between(lo, hi)]
    t = g.groupby("tier", observed=True).agg(
        n=("took", "size"), price=("offered_rate_pct", "mean"),
        took=("took", "mean"), booked=("took", "sum"))
    t["mix"] = t["booked"] / t["booked"].sum()
    out[name] = t
for tier in out["flat"].index:
    f, t = out["flat"].loc[tier], out["tiers"].loc[tier]
    print(f"{tier:<9}{f['price']:>11.1f}%{f['took']:>6.0%}"
          f"{f['mix']:>6.0%}{t['price']:>13.1f}%{t['took']:>6.0%}"
          f"{t['mix']:>6.0%}")

flat = ap[ap["app_date"].between(*periods["flat"])]
took, left = flat[flat["took"]], flat[~flat["took"]]
print(f"\nOne price for all, 2017-2018: {len(flat):,} approved, "
      f"{flat['took'].mean():.0%} took it")
for name, g in (("took the loan", took), ("walked away", left)):
    print(f"  {name:<14}{len(g):>6,}  Mark II-R {g['m2r'].mean():.0f}"
          f", promised bad rate {g['promise'].mean():.2%}")
same = flat["promise"].mean()
print(f"  had all taken it alike, the book's promise: {same:.2%}")

tiers = ap[ap["app_date"].between(*periods["tiers"])]
rate = out["flat"]["took"]
w = tiers["tier"].map(rate).astype(float)
mix = w.groupby(tiers["tier"], observed=True).sum()
print("\nThe tiers' approvals, booked at flat-price take-up:")
print("  mix " + "  ".join(f"{k} {v:.0%}" for k, v in
                           (mix / mix.sum()).items()))
(ROOT / "code" / "12" / "04_flat_and_tiers.json").write_text(
    json.dumps({k: v.reset_index().astype({"tier": str})
                .to_dict("records") for k, v in out.items()},
               indent=1) + "\n")
