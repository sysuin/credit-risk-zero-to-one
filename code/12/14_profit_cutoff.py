# Does the cut-off of 554 survive on profit? What an applicant at each
# Mark II-R score is worth, with capital charged and money discounted.
import json
import sys

import pandas as pd

import fernhill
from ballast import pricing
from ballast.config import ROOT
from ballast.scorecard import reject

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, market, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
costs, m = pricing.Costs(lgd=lgd), market(con)
oot = reject.frames(reject.applicants())["oot"][["app_id"]]
f = oot.merge(a, on="app_id")
ap = a[a["decision"].eq("approve") & a["price_test_arm"].isna()
       & a["app_date"].between("2023-01-01", "2024-12-31")]
edges = list(range(535, 606, 5))
for d in (f, ap):
    d["band"] = pd.cut(d["m2r"], edges, right=False)
took = ap.groupby("band", observed=True).agg(
    took=("outcome", lambda x: x.eq("booked").mean()),
    price=("offered_rate_pct", "mean"))
rows = []
for b, g in f.groupby("band", observed=True):
    s, amt = g["m2r"].mean(), int(g["amount_requested_cents"].mean())
    term = int(round(g["term_requested_months"].mean() / 12) * 12)
    price = took.loc[b, "price"]
    pp = float(fp.annual(s))
    row = {"band": int(b.left), "n": len(g),
           "took": took.loc[b, "took"], "price": price}
    for name, k in (("book", 1.0), ("adverse", 1.25)):
        pd_ = float(fd.annual(s)) * k
        v = pricing.value(amt, price, term, pd_, pp, m, costs)
        row[name] = v.economic / 100
        row[name + "_pd"] = pd_
    rows.append(row)
t = pd.DataFrame(rows)
print(f"{len(f):,} applicants past the rules, Jan 2023-Jun 2024. "
      "Value of a\nbooked loan at its band's price today, after the "
      "charge for capital")
print(f"{'Mark II-R':<10}{'apps':>6}{'took':>6}{'price':>7}{'PD':>7}"
      f"{'value':>7}{'PD x1.25':>9}{'value':>7}")
for r in t.itertuples():
    print(f"{r.band}-{r.band + 4:<6}{r.n:>6,}{r.took:>6.0%}"
          f"{r.price:>7.2f}{r.book_pd:>7.1%}{r.book:>7,.0f}"
          f"{r.adverse_pd:>9.1%}{r.adverse:>7,.0f}")
print("\nExpected value per 1,000 applicants, approving down to:")
v = f[["m2r", "band"]].merge(t.assign(band=pd.cut(t["band"], edges,
                                                  right=False)),
                             on="band")
cuts = {}
for cut in (540, 545, 550, 554, 558, 565, 570):
    ok = v["m2r"] >= cut
    cuts[cut] = [(v.loc[ok, "took"] * v.loc[ok, c]).sum() / len(f)
                 * 1000 for c in ("book", "adverse")]
    print(f"  {cut}: ${cuts[cut][0]:>9,.0f} at the book's PD, "
          f"${cuts[cut][1]:>9,.0f} at 1.25 times it")
for i, name in enumerate(("the book's PD", "1.25 times it")):
    best = max(cuts, key=lambda c: cuts[c][i])
    print(f"Best of these at {name}: {best}")
(ROOT / "code" / "12" / "14_profit_cutoff.json").write_text(
    json.dumps(t.round(5).to_dict("records"), indent=1) + "\n")
