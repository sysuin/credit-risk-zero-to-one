# Each ratio on its own: how well it ranks the reviews followed by a
# default, and what a defaulter's ratio looked like beside the rest.
import numpy as np

import fernhill
from ballast.commercial import rating as rt
from ballast.scorecard import metrics as mt

con = fernhill.connect()
dev = rt.reviews(con).query("window_complete")
dev = dev.join(rt.features(dev)[["size"]])
bad = dev.default_12m
# (column, label, sign: +1 if a higher value is safer)
show = [("leverage", "debt / EBITDA", -1),
        ("interest_cover", "EBITDA / interest", +1),
        ("net_margin", "net margin", +1),
        ("dscr", "DSCR (5-year basis)", +1),
        ("current_ratio", "current ratio", +1),
        ("equity_ratio", "equity / assets", +1),
        ("ebitda_margin", "EBITDA margin", +1),
        ("size", "size (log10 revenue)", +1),
        ("cash_conversion", "cash conversion", +1),
        ("receivable_days", "receivable days", -1),
        ("cash_cycle", "cash cycle, days", -1),
        ("cash_days", "cash, days of costs", +1)]
print(f"{'ratio':<22}{'Gini':>7}{'defaulters':>12}{'others':>9}")
for col, label, sign in show:
    x = dev[col].astype(float)
    x = x.fillna(np.nanmax(x) if sign < 0 else np.nanmin(x))
    g = mt.gini(sign * x, bad)
    print(f"{label:<22}{g:>+7.3f}{x[bad == 1].median():>12.2f}"
          f"{x[bad == 0].median():>9.2f}")
F = rt.features(dev)
c = F.corr()
print("\ncorrelations of the model's inputs")
print(f"{'':<10}" + "".join(f"{rt.SHORT[n]:>10}" for n in F.columns))
for n in F.columns:
    print(f"{rt.SHORT[n]:<10}" + "".join(f"{c.loc[n, k]:>10.2f}"
                                         for k in F.columns))
