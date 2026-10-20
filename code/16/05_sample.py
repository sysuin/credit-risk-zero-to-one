# The rating model's sample: every review whose following year has
# passed, and the defaults in that year. There are not many.
import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv.window_complete]
print(f"reviews {len(rv):,}; with a complete year after them "
      f"{len(dev):,}")
print(f"{'review':<8}{'accounts':>9}{'clients':>9}{'defaults':>10}"
      f"{'rate':>8}")
for y, g in dev.groupby(dev.review_date.dt.year):
    print(f"{y:<8}{g.fiscal_year.iloc[0]:>9}{len(g):>9}"
          f"{g.default_12m.sum():>10}{g.default_12m.mean():>8.1%}")
n, d = len(dev), dev.default_12m.sum()
print(f"{'all':<8}{'':>9}{n:>9,}{d:>10}{d / n:>8.2%}")
print(f"\ndifferent clients that defaulted: "
      f"{dev[dev.default_12m == 1].company_id.nunique()}")
print(f"defaults per candidate input, at 10 per input: "
      f"{d / 10:.1f} inputs")
