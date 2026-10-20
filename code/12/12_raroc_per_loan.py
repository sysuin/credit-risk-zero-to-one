# The risk-adjusted return on capital of every personal loan Fernhill
# booked in 2025, at the price it was booked at.
import json
import sys

import numpy as np
import pandas as pd

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, mark1_tier, market, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
costs = pricing.Costs(lgd=lgd)
loans = a[a["outcome"].eq("booked") & a["app_date"].dt.year.eq(2025)
          ].merge(con.execute("SELECT account_id, amount_cents, "
                              "term_months, rate_pct, open_date "
                              "FROM accounts").df(), on="account_id")
months = {m: market(con, m) for m in
          pd.to_datetime(loans["open_date"]).dt.to_period("M")
          .dt.end_time.dt.strftime("%Y-%m-%d").unique()}
out = []
for r in loans.itertuples():
    m = months[pd.Timestamp(r.open_date).to_period("M")
               .end_time.strftime("%Y-%m-%d")]
    v = pricing.value(int(r.amount_cents), r.rate_pct,
                      int(r.term_months), float(fd.annual(r.m2r)),
                      float(fp.annual(r.m2r)), m, costs)
    out.append((v.raroc, v.economic, v.balance_years))
loans[["raroc", "economic", "years"]] = np.array(out)
q = np.percentile(loans["raroc"], [10, 25, 50, 75, 90])
print(f"{len(loans):,} loans booked in 2025; hurdle "
      f"{costs.hurdle_pct:.0f}%")
print("RAROC  p10 {:.0%}  p25 {:.0%}  median {:.0%}  p75 {:.0%}  "
      "p90 {:.0%}".format(*q))
whole = (loans["raroc"] * loans["years"]).sum() / loans["years"].sum()
below = loans["raroc"] < costs.hurdle_pct / 100
print(f"Whole book {whole:.0%}; below the hurdle "
      f"{below.mean():.1%} ({below.sum()} loans), losing money "
      f"{(loans['raroc'] < 0).mean():.1%}")

loans["band"] = pd.cut(loans["m2r"], [0, 560, 570, 580, 590, 600, 610,
                                      999], right=False)
loans["tier"] = mark1_tier(loans["mark1_score"]).array
print(f"\n{'Mark II-R':<11}{'loans':>6}{'rate':>7}{'PD':>6}{'RAROC':>7}"
      f"{'below':>7}")
for b, g in loans.groupby("band", observed=True):
    lo, hi = int(b.left), int(b.right) - 1
    name = f"<{hi + 1}" if lo == 0 else (f"{lo}+" if hi > 900
                                        else f"{lo}-{hi}")
    w = (g["raroc"] * g["years"]).sum() / g["years"].sum()
    print(f"{name:<11}{len(g):>6,}{g['rate_pct'].mean():>7.2f}"
          f"{fd.annual(g['m2r']).mean():>6.1%}{w:>7.0%}"
          f"{(g['raroc'] < costs.hurdle_pct / 100).mean():>7.0%}")
bad = loans[below]
print("\nThe loans below the hurdle, by Mark I price tier:")
print("  " + "  ".join(f"{k} {v}" for k, v in
                       bad["tier"].value_counts().sort_index().items()))
print(f"  median Mark II-R {bad['m2r'].median():.0f}; "
      f"median rate {bad['rate_pct'].median():.2f}%")
(ROOT / "code" / "12" / "12_raroc_per_loan.json").write_text(
    json.dumps({"raroc": np.round(loans["raroc"], 4).tolist(),
                "hurdle": costs.hurdle_pct / 100}) + "\n")
