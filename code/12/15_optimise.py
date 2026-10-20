# The price that earns most in each new tier, within what the test can
# vouch for, and the limits Fernhill sets on itself: the 2026 grid.
import json
import sys

import numpy as np
import pandas as pd

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, market, scored  # noqa: E402

SLOPE = -0.403          # log odds per point, from listing 07's model
con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
costs, m = pricing.Costs(lgd=lgd), market(con)
grid = pricing.Grid(edges=(565, 580, 595, 610), rates=(0,) * 5,
                    at_ftp_pct=0)
names = grid.labels(550, 652)
ap = a[a["decision"].eq("approve") & a["price_test_arm"].isna()
       & a["app_date"].between("2024-01-01", "2025-12-31")
       & (a["m2r"] >= 550)].copy()
ap["tier"] = grid.tier(ap["m2r"])
dec = ap[ap["app_date"] >= "2025-12-01"]
rows = []
print(f"{'Mark II-R':<10}{'today':>6}{'took':>6}{'floor':>7}{'best':>6}"
      f"{'took':>6}{'per approval':>13}{'at best':>8}")
for k, g in ap.groupby("tier"):
    lo = 550 if k == 0 else grid.edges[k - 1]
    s = g["m2r"].mean()
    pd_, pp = float(fd.annual(s)), float(fp.annual(s))
    amt = int(g["offered_amount_cents"].mean())
    term = int(round(g["term_requested_months"].mean() / 12) * 12)
    today = float(dec.loc[dec["tier"] == k, "offered_rate_pct"].mean())
    p0 = g["outcome"].eq("booked").mean()
    floor = pricing.floor_rate(amt, term, float(fd.annual(lo)),
                               float(fp.annual(lo)), m, costs)

    def earns(r):
        return pricing.value(amt, r, term, pd_, pp, m, costs).economic

    rates = np.round(np.arange(today - 1.5, today + 1.51, 0.25), 2)
    best, t = pricing.best_rate(rates, p0, SLOPE, today, earns)
    now = p0 * earns(today) / 100
    b = t.set_index("rate").loc[best]
    print(f"{names[k]:<10}{today:>6.2f}{p0:>6.0%}{floor:>7.2f}"
          f"{best:>6.2f}{b['take_up']:>6.0%}{now:>13,.0f}"
          f"{b['per_approval'] / 100:>8,.0f}")
    rows.append({"tier": names[k], "today": today, "took": p0,
                 "floor": floor, "best": best, "s": s, "amt": amt,
                 "term": term, "pd": pd_, "pp": pp})
print("(per approval: take-up times what a loan earns after every "
      "cost,\n in dollars; best searched within 1.5 points of today's "
      "price)")
r = pd.DataFrame(rows)

CAP = 3.0               # Fernhill's fair-value limit: margin over floor
r["capped"] = np.clip(np.minimum(r["best"], r["floor"] + CAP),
                      r["today"] - 1.5, r["today"] + 1.5)
r["grid"] = pricing.monotone(np.maximum(np.floor(r["capped"] * 20),
                                      np.ceil(r["floor"] * 20)) / 20)
print(f"\nLimits: no tier below its floor, none more than {CAP:.0f} "
      "points above it,\nnone cheaper than a safer tier, every move "
      "within the tested\n1.5 points")
total = {"today": 0.0, "best": 0.0, "grid": 0.0}
loans = dict.fromkeys(total, 0.0)
w = ap["tier"].value_counts(normalize=True).sort_index()
print(f"{'Mark II-R':<10}{'today':>7}{'best':>7}{'2026':>7}"
      f"{'margin':>8}{'took':>6}{'RAROC':>7}")
for k, x in r.iterrows():
    for col in total:
        up = float(pricing.shift_take_up(x["took"], SLOPE,
                                         x[col] - x["today"]))
        v = pricing.value(x["amt"], x[col], x["term"], x["pd"],
                          x["pp"], m, costs)
        total[col] += w[k] * up * v.economic / 100
        loans[col] += w[k] * up * 100
    print(f"{x['tier']:<10}{x['today']:>7.2f}{x['best']:>7.2f}"
          f"{x['grid']:>7.2f}{x['grid'] - x['floor']:>8.2f}{up:>6.0%}"
          f"{v.raroc:>7.0%}")
print("(took and RAROC at the 2026 price, for the tier's average "
      "applicant)")
for k in total:
    print(f"  {k:<6} value per approval ${total[k]:,.0f}, "
          f"loans per 100 approvals {loans[k]:.1f}")
x = r.iloc[0]
print(f"\nAt the line, priced {x['grid']:.2f}%: what a booked loan is "
      "worth")
for lo, hi in ((546, 549), (550, 553), (554, 557)):
    s = (lo + hi) / 2
    v = [pricing.value(x["amt"], x["grid"], x["term"],
                       k * float(fd.annual(s)), float(fp.annual(s)),
                       m, costs).economic / 100 for k in (1.0, 1.25)]
    print(f"  Mark II-R {lo}-{hi}: ${v[0]:>4,.0f} at the book's PD, "
          f"${v[1]:>5,.0f} at 1.25 times it")
(ROOT / "code" / "12" / "15_optimise.json").write_text(json.dumps(
    {"edges": list(grid.edges), "rates": r["grid"].round(2).tolist(),
     "floor": r["floor"].round(2).tolist(),
     "today": r["today"].round(2).tolist(), "labels": names,
     "ftp": pricing.value(1_200_000, 12.0, 36, 0.02, 0.2, m,
                          costs).ftp_pct}, indent=1) + "\n")
