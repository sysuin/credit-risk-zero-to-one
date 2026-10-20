# Fernhill's commercial facilities under the standardised approach:
# an agency letter where the company has one, unrated otherwise.
import fernhill
import numpy as np
import pandas as pd
from ballast import capital

con = fernhill.connect()
s = capital.standardised(capital.book(con), capital.provisions())
c = s[s.segment == "commercial"].copy()
c["bucket"] = c.agency.fillna(pd.Series(np.where(
    c.sales_m < capital.SME_SALES_M,
    "unrated, small", "unrated"), index=c.index))
order = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "unrated, small",
         "unrated"]
g = c.groupby("bucket").agg(
    firms=("company_id", "nunique"), drawn=("drawn_cents", "sum"),
    undrawn=("undrawn_cents", "sum"), ead=("sa_ead", "sum"),
    rwa=("sa_rwa", "sum"), rw=("sa_rw", "first")).reindex(order)
print(f"{'rating':<16}{'firms':>6}{'drawn':>8}{'undrawn':>9}{'EAD':>8}"
      f"{'weight':>8}{'RWA':>8}")
for k, r in g.iterrows():
    print(f"{k:<16}{r.firms:>6.0f}{r.drawn / 1e8:>8,.0f}"
          f"{r.undrawn / 1e8:>9,.0f}{r.ead / 1e8:>8,.0f}{r.rw:>8.0%}"
          f"{r.rwa / 1e8:>8,.0f}")
t = g.sum()
print(f"{'all':<16}{c.company_id.nunique():>6}{t.drawn / 1e8:>8,.0f}"
      f"{t.undrawn / 1e8:>9,.0f}{t.ead / 1e8:>8,.0f}"
      f"{t.rwa / t.ead:>8.1%}{t.rwa / 1e8:>8,.0f}")
print("$m; undrawn: revolvers' headroom, converted at "
      f"{capital.SA_CCF['commercial_revolver']:.0%}")
rated = c.agency.notna()
print(f"rated: {c.loc[rated, 'company_id'].nunique()} firms, "
      f"{c.loc[rated, 'sa_ead'].sum() / t.ead:.0%} of EAD")
