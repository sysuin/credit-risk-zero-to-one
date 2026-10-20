# Exercise 28.4: the CDS spread at which protection on $20m of Elm
# Juniper Foods costs what its better loan earns, and the PD implied.
from ballast import securitisation as sec

NOTIONAL, MARGIN_BPS = 20_000_000_00, 225
c = sec.cds_cost(NOTIONAL, MARGIN_BPS)
print(f"break-even spread {MARGIN_BPS} bp: premium "
      f"${c['premium_a_year'] / 100:,.0f} a year")
print(f"implied hazard {c['hazard']:.2%} a year, "
      f"one-year PD {c['pd_1y']:.2%}")
