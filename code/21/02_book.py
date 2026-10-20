# Everything Fernhill had lent, or promised to lend, on 31 December
# 2025: one row per account or facility, drawn and undrawn.
import fernhill
from ballast import capital

con = fernhill.connect()
b = capital.book(con)
g = b.groupby("product").agg(
    n=("account_id", "size"), drawn=("drawn_cents", "sum"),
    undrawn=("undrawn_cents", "sum"), dflt=("in_default", "sum"))
print(f"{'product':<20}{'exposures':>10}{'drawn $m':>10}"
      f"{'undrawn $m':>12}{'in default':>12}")
for p, r in g.iterrows():
    print(f"{p:<20}{r.n:>10,}{r.drawn / 1e8:>10,.1f}"
          f"{r.undrawn / 1e8:>12,.1f}{r.dflt:>12,}")
print(f"{'all':<20}{g.n.sum():>10,}{g.drawn.sum() / 1e8:>10,.1f}"
      f"{g.undrawn.sum() / 1e8:>12,.1f}{g.dflt.sum():>12,}")

src = con.execute("""
    SELECT (SELECT sum(balance_cents) FROM performance
            WHERE month = '2025-12-31'
              AND status IN ('up_to_date', 'arrears', 'default')),
           (SELECT sum(drawn_cents) FROM facility_months
            WHERE month = '2025-12-31')""").fetchone()
print(f"\nsource: performance ${src[0] / 100:,.0f} + facilities "
      f"${src[1] / 100:,.0f}")
print(f"book:   ${b.drawn_cents.sum() / 100:,.0f}")
big = (b.segment == "retail") & (b.cls == "corporate")
print(f"small-business accounts over $1m, treated as companies: "
      f"{big.sum()}")
