# Two estimates of price response from history alone, without the
# test: across the tiers, and through the rate rises of 2022-2023.
import sys

import numpy as np

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import mark1_tier, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
ap = a[a["decision"].eq("approve") & a["override"].isna()
       & a["price_test_arm"].isna()].copy()
ap["took"] = ap["outcome"].eq("booked").astype(int)
ap["tier"] = mark1_tier(ap["mark1_score"]).array

y24 = ap[ap["app_date"].dt.year.eq(2024)]
slope = np.polyfit(y24["offered_rate_pct"], y24["took"], 1)[0]
r = pricing.fit_take_up(y24["took"], y24["offered_rate_pct"])
print(f"Across the tiers, 2024 ({len(y24):,} approvals at policy "
      "price)")
for tier, g in y24.groupby("tier", observed=True):
    price = g["offered_rate_pct"].mean()
    print(f"  Mark I {tier:<8} price {price:5.2f}%  took "
          f"{g['took'].mean():.0%}")
print(f"  take-up per point of price: {100 * slope:+.1f} points; "
      f"log odds {r.params['change']:.3f}")

top = ap[ap["tier"].eq("660+")
         & ap["app_date"].between("2019-07-01", "2025-12-31")].copy()
top["half"] = (top["app_date"].dt.year.astype(str) + " H"
               + np.where(top["app_date"].dt.month <= 6, "1", "2"))
h = top.groupby("half").agg(price=("offered_rate_pct", "mean"),
                            took=("took", "mean"), n=("took", "size"))
print("\nThrough time, Mark I 660+ only")
for k in ("2019 H2", "2021 H2", "2022 H2", "2023 H2", "2025 H2"):
    print(f"  {k}  price {h.loc[k, 'price']:5.2f}%  took "
          f"{h.loc[k, 'took']:.0%}  ({h.loc[k, 'n']:,} approvals)")
s = np.polyfit(h["price"], h["took"], 1)[0]
print(f"  take-up per point, {len(h)} half-years: "
      f"{100 * s:+.1f} points")
