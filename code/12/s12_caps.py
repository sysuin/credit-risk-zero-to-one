# Exercise 12.4: the 2026 grid under a fair-value cap of 2, 3 and 4
# points over each tier's floor.
import sys

import numpy as np

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, market, scored  # noqa: E402

SLOPE = -0.403
con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
costs, m = pricing.Costs(lgd=lgd), market(con)
grid = pricing.Grid(edges=(565, 580, 595, 610), rates=(0,) * 5,
                    at_ftp_pct=0)
ap = a[a["decision"].eq("approve") & a["price_test_arm"].isna()
       & a["app_date"].between("2024-01-01", "2025-12-31")
       & (a["m2r"] >= 550)].copy()
ap["tier"] = grid.tier(ap["m2r"])
dec = ap[ap["app_date"] >= "2025-12-01"]
share = ap["tier"].value_counts(normalize=True).sort_index()
tiers = []
for k, g in ap.groupby("tier"):
    lo = 550 if k == 0 else grid.edges[k - 1]
    s = g["m2r"].mean()
    t = {"pd": float(fd.annual(s)), "pp": float(fp.annual(s)),
         "amt": int(g["offered_amount_cents"].mean()),
         "term": 12 * int(round(g["term_requested_months"].mean()
                                / 12)),
         "today": float(dec.loc[dec["tier"] == k,
                                "offered_rate_pct"].mean()),
         "p0": g["outcome"].eq("booked").mean()}
    t["floor"] = pricing.floor_rate(t["amt"], t["term"],
                                    float(fd.annual(lo)),
                                    float(fp.annual(lo)), m, costs)

    def earns(r, t=t):
        return pricing.value(t["amt"], r, t["term"], t["pd"], t["pp"],
                             m, costs).economic

    rates = np.round(np.arange(t["today"] - 1.5, t["today"] + 1.51,
                               0.25), 2)
    t["best"], _ = pricing.best_rate(rates, t["p0"], SLOPE, t["today"],
                                     earns)
    t["earns"] = earns
    tiers.append(t)
print(f"{'cap':<5}{'prices, riskiest tier first':<36}{'value':>8}"
      f"{'loans':>7}")
for cap in (2.0, 3.0, 4.0):
    capped = [np.clip(min(t["best"], t["floor"] + cap),
                      t["today"] - 1.5, t["today"] + 1.5)
              for t in tiers]
    price = pricing.monotone([max(np.floor(c * 20), np.ceil(t["floor"]
                                                            * 20)) / 20
                              for c, t in zip(capped, tiers)])
    value = loans = 0.0
    for k, (t, r) in enumerate(zip(tiers, price)):
        up = float(pricing.shift_take_up(t["p0"], SLOPE,
                                         r - t["today"]))
        value += share[k] * up * t["earns"](r) / 100
        loans += share[k] * up * 100
    print(f"{cap:<5.0f}" + " ".join(f"{r:6.2f}" for r in price)
          + f"{value:>7,.0f}{loans:>7.1f}")
print("(value: dollars per approval; loans: per 100 approvals)")
