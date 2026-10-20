# Fernhill's own rating model: can a validator rebuild its grades from
# what its document says it reads (leverage, cover and size), and what
# did the analysts' holds of its grades do?
import textwrap

import numpy as np
import statsmodels.api as sm

import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
F = rt.features(rv)
for cols in (["ln_leverage", "ln_cover", "size"], list(F.columns)):
    r = sm.OLS(rv["model_grade"].astype(float),
               sm.add_constant(F[cols])).fit()
    fitted = np.clip(np.round(r.fittedvalues), 1, 10)
    gap = (fitted - rv["model_grade"]).abs()
    print(f"{' + '.join(cols)}:\n  R-squared {r.rsquared:.3f}; grade "
          f"reproduced {(gap == 0).mean():.1%}, within one notch "
          f"{(gap <= 1).mean():.1%}")

m = rt.moves(rv)
m = m[m["window_complete"] & (m["wanted"] > 0)]
print("\nReviews where the model wanted a downgrade (complete years)")
print(f"{'analyst':<9}{'reviews':>8}{'defaulted':>11}{'grade PD':>10}"
      f"{'model PD':>10}")
for what, h in (("moved", False), ("held", True)):
    g = m[m["held_found"] == h]
    print(f"{what:<9}{len(g):>8}{g['default_12m'].mean():>11.1%}"
          f"{g['grade'].map(rt.pd_of).mean():>10.2%}"
          f"{g['model_grade'].map(rt.pd_of).mean():>10.2%}")
cols = [c for c, *_ in con.execute("DESCRIBE ratings").fetchall()]
print(f"Holds flagged in the ratings table: {int(rv['held'].sum())}; "
      "its columns:")
print(textwrap.fill(", ".join(cols), 66, initial_indent="  ",
                    subsequent_indent="  "))
