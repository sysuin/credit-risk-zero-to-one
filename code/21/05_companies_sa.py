# Fernhill's commercial facilities under the standardised approach:
# an agency letter where the company has one, unrated otherwise.
import fernhill
from ballast import capital

con = fernhill.connect()
sa = capital.standardised(capital.book(con), capital.provisions())
firms = sa[sa.segment == "commercial"].copy()

# Each facility's bucket: its agency letter, or unrated (small or not).
small = firms.sales_m < capital.SME_SALES_M
rated = firms.agency.notna()
firms["bucket"] = "unrated"
firms.loc[small, "bucket"] = "unrated, small"
firms.loc[rated, "bucket"] = firms.agency[rated]

order = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "unrated, small",
         "unrated"]
g = firms.groupby("bucket").agg(
    firms=("company_id", "nunique"), drawn=("drawn_cents", "sum"),
    undrawn=("undrawn_cents", "sum"), ead=("sa_ead", "sum"),
    rwa=("sa_rwa", "sum"), rw=("sa_rw", "first")).reindex(order)
print(f"{'rating':<16}{'firms':>6}{'drawn':>8}{'undrawn':>9}{'EAD':>8}"
      f"{'weight':>8}{'RWA':>8}")
for bucket, row in g.iterrows():
    print(f"{bucket:<16}{row.firms:>6.0f}{row.drawn / 1e8:>8,.0f}"
          f"{row.undrawn / 1e8:>9,.0f}{row.ead / 1e8:>8,.0f}"
          f"{row.rw:>8.0%}{row.rwa / 1e8:>8,.0f}")

# The whole commercial book; its weight is total RWA over total EAD.
t = g.sum()
print(f"{'all':<16}{firms.company_id.nunique():>6}"
      f"{t.drawn / 1e8:>8,.0f}{t.undrawn / 1e8:>9,.0f}"
      f"{t.ead / 1e8:>8,.0f}{t.rwa / t.ead:>8.1%}{t.rwa / 1e8:>8,.0f}")
print("$m; undrawn: revolvers' headroom, converted at "
      f"{capital.SA_CCF['commercial_revolver']:.0%}")
rated_ead = firms.loc[rated, "sa_ead"].sum()
print(f"rated: {firms.loc[rated, 'company_id'].nunique()} firms, "
      f"{rated_ead / t.ead:.0%} of EAD")
