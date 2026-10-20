# Conversion factors backtested out of time: fitted on the defaults to
# 2022, applied to the balances and limits a year before each default
# of 2023-2025, against the exposure that turned out.
import pandas as pd

import fernhill
from ballast.parameters import ead

con = fernhill.connect()
CUT = pd.Timestamp("2022-12-31")
print(f"{'':<14}{'fit n':>6}{'CCF':>6}{'test n':>8}{'predicted':>12}"
      f"{'actual':>12}{'ratio':>7}")
for p in ("card", "sme_overdraft"):
    s = ead.ccf_sample(con, p)
    s = s[s["missed0"] == 0]
    dm = pd.to_datetime(s["default_month"])
    fit, test = s[dm <= CUT], s[dm > CUT]
    table = ead.fit_ccf(fit)
    if p != "card":
        table["ccf"] = ead.pooled_ccf(fit)
    pred = ead.exposure(test["b0"], test["l0"], table).sum()
    act = test["ead"].sum()
    print(f"{p:<14}{len(fit):>6,}{ead.pooled_ccf(fit):>6.2f}"
          f"{len(test):>8,}{f'${pred / 100:,.0f}':>12}"
          f"{f'${act / 100:,.0f}':>12}{pred / act:>7.3f}")
    if p == "card":
        edges = list(ead.BANDS)
        band = pd.cut(test["u0"], edges, right=False)
        for b, g in test.groupby(band, observed=True):
            pr = ead.exposure(g["b0"], g["l0"], table).sum()
            ac = g["ead"].sum()
            print(f"  used {b.left:.0%}+{'':<9}{len(g):>8,}"
                  f"{f'${pr / 100:,.0f}':>12}{f'${ac / 100:,.0f}':>12}"
                  f"{pr / ac:>7.3f}")
rv = ead.revolver_sample(con)
dm = pd.to_datetime(rv["default_month"])
loo = [ead.pooled_ccf(rv.drop(i)) for i in rv.index]
print(f"\nRevolvers: {len(rv)} defaults, {int((dm > CUT).sum())} after "
      f"2022; CCF {ead.pooled_ccf(rv):.2f};\nleaving one out moves it "
      f"between {min(loo):.2f} and {max(loo):.2f}; fitted to 2022 "
      f"{ead.pooled_ccf(rv[dm <= CUT]):.2f},\nafter 2022 "
      f"{ead.pooled_ccf(rv[dm > CUT]):.2f}")
