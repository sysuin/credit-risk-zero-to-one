# What each Mark I band's loans earned under the flat price and under
# the tiers: cash to December 2025, after funding and running costs.
import sys

import fernhill
from ballast.config import ROOT
from ballast.decision import strategy

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import mark1_tier, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
eco = strategy.loan_economics(con, "personal", opex_pct=2.5)
d = a[a["outcome"].eq("booked")].merge(
    eco[["account_id", "amount_cents", "profit"]], on="account_id")
d["tier"] = mark1_tier(d["mark1_score"]).array
print(f"{'':<9}{'flat 2017-18':>21}{'tiers Apr 2019-Mar 2020':>27}")
print(f"{'Mark I':<9}{'loans':>7}{'each':>7}{'of lent':>8}"
      f"{'loans':>11}{'each':>7}{'of lent':>8}")
rows = {}
for name, lo, hi in (("flat", "2017-01-01", "2018-12-31"),
                     ("tiers", "2019-04-01", "2020-03-31")):
    g = d[d["app_date"].between(lo, hi)]
    rows[name] = g.groupby("tier", observed=True).agg(
        loans=("profit", "size"), each=("profit", "mean"),
        profit=("profit", "sum"), lent=("amount_cents", "sum"))
    rows[name].loc["all"] = [len(g), g["profit"].mean(),
                             g["profit"].sum(), g["amount_cents"].sum()]
for tier in rows["flat"].index:
    f, t = rows["flat"].loc[tier], rows["tiers"].loc[tier]
    print(f"{tier:<9}{f['loans']:>7,.0f}{f['each'] / 100:>7,.0f}"
          f"{f['profit'] / f['lent']:>8.1%}{t['loans']:>11,.0f}"
          f"{t['each'] / 100:>7,.0f}{t['profit'] / t['lent']:>8.1%}")
print("(profit per loan in dollars, and as a share of the amount lent)")
