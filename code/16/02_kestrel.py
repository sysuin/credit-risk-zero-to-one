# Kestrel Cedar Foods: five years at grade 7 while the model moved.
import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
k = rv[rv.name == "Kestrel Cedar Foods"]
print(f"{k.name.iloc[0]} ({k.company_id.iloc[0]}, {k.sector.iloc[0]})")
print(f"{'review':<8}{'accounts':>9}{'debt/EBITDA':>13}"
      f"{'cover':>8}{'model':>7}{'grade':>7}  held")
for _, r in k.iterrows():
    held = "yes" if r.held else ""
    print(f"{r.review_date:%Y}{r.fiscal_year:>11}{r.leverage:>12.2f}x"
          f"{r.interest_cover:>7.2f}x{r.model_grade:>7}{r.grade:>7}"
          f"  {held}")
last = k.iloc[-1]
print(f"\nPD at grade {last.grade}: {rt.pd_of(last.grade):.1%}; "
      f"at the model's {last.model_grade}: "
      f"{rt.pd_of(last.model_grade):.0%}")
