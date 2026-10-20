# Meridian's price: the rate it would pay, what a year of the facility
# earns Fernhill at different drawings, and a provisional loss cost.
import fernhill
from _meridian import MARGIN_BPS, analysis, book_loss_cost
from ballast.commercial import structure as st

con = fernhill.connect()
a = analysis(con)
s, limit = a["s"], a["limit"]
ref = con.execute("""SELECT policy_rate_pct FROM market_rates
                     WHERE month = '2025-12-31'""").fetchone()[0]
paid = s.loc["interest", 2025] / s.loc["total_debt", 2025]
print(f"reference rate (policy rate, Dec 2025) {ref:.2f}%")
print(f"  + margin {MARGIN_BPS} bps = {ref + MARGIN_BPS / 100:.2f}%"
      f"; Meridian paid about {paid:.1%} in 2025")

print(f"\na year of a ${limit / 1e8:.0f}m facility, $000")
print(f"  {'drawn':>7}{'margin':>9}{'undrawn fee':>13}"
      f"{'arrangement':>13}{'total':>8}")
for share in (0.30, 0.38, 0.60, 0.90):
    inc = st.facility_income(limit, round(limit * share), MARGIN_BPS)
    print(f"  {share:>7.0%}{inc.margin / 1e5:>9,.0f}"
          f"{inc.commitment_fee / 1e5:>13,.0f}"
          f"{inc.arrangement_fee / 1e5:>13,.0f}"
          f"{inc.total / 1e5:>8,.0f}")

# Fernhill's book averages, not Meridian's grade (Chapter 16's).
el = book_loss_cost(con, limit)
print("\nprovisional loss cost, Fernhill's book averages:")
print(f"  default rate {el['pd']:.2%} a year x loss {el['loss']:.0%}"
      f" x drawn {el['drawn']:.0%} of the limit")
print(f"  = ${el['cost'] / 1e5:,.0f}k a year")
