# Exercise 15.4: the margin at which a year's income at 38% drawn is
# three times the provisional loss cost.
import fernhill
from _meridian import analysis
from ballast.commercial import structure as st

con = fernhill.connect()
a = analysis(con)
limit, el = a["limit"], a["loss_cost"]
drawn = round(limit * 0.38)
fixed = st.facility_income(limit, drawn, 0).arrangement_fee
per_bp = (st.facility_income(limit, drawn, 100).total - fixed) / 100
need = (3 * el - fixed) / per_bp
print(f"loss cost ${el / 1e5:,.0f}k; three times ${3 * el / 1e5:,.0f}k")
print(f"income per basis point of margin at 38% drawn: "
      f"${per_bp / 100:,.0f}")
print(f"margin needed: {need:.0f} bps")
