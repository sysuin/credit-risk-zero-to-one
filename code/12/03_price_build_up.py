# A $12,000 three-year personal loan priced from its pieces, for the
# typical borrower in each of Fernhill's four price tiers.
import json
import sys

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, mark1_tier, market, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
costs = pricing.Costs(lgd=lgd)
m = market(con)
ap = a[a["decision"].eq("approve") & a["price_test_arm"].isna()
       & a["app_date"].dt.year.eq(2025)
       & a["app_date"].dt.month.eq(12)].copy()
ap["tier"] = mark1_tier(ap["mark1_score"]).array
print(f"Costs: running {costs.opex_pct}%, capital {costs.capital_pct}%"
      f" of balance at {costs.hurdle_pct}%, LGD {costs.lgd:.0%}")
print(f"{'Mark I':<9}{'price':>6}{'MkII-R':>7}{'PD':>6}{'fund':>6}"
      f"{'run':>5}{'loss':>6}{'cap':>5}{'floor':>6}{'margin':>7}")
rows = []
for t, g in ap.groupby("tier", observed=True):
    s = round(g["m2r"].mean())
    pd_, pp = float(fd.annual(s)), float(fp.annual(s))
    w = pricing.waterfall(1_200_000, 36, pd_, pp, m, costs)
    price = g["offered_rate_pct"].median()
    rows.append({"tier": t, "price": price, "score": s, **w})
    print(f"{t:<9}{price:>6.1f}{s:>7}{pd_:>6.1%}{w['funding']:>6.2f}"
          f"{w['operating']:>5.1f}{w['expected_loss']:>6.2f}"
          f"{w['capital']:>5.2f}{w['floor']:>6.2f}"
          f"{price - w['floor']:>7.2f}")
print("(% a year of the balance; PD is the default rate a year)")
(ROOT / "code" / "12" / "03_price_build_up.json").write_text(
    json.dumps(rows, indent=1) + "\n")
