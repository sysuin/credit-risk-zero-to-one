# The limit on distributions, tested on what Meridian actually paid:
# each year's dividend against what the rule would have allowed.
import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
r = sp.ratios(s)
print(f"rule: up to {st.PAYOUT_CAP:.0%} of last year's net income, "
      f"leverage <= {st.DIVIDEND_MAX_LEVERAGE:.2f}x")
print("\n$000   prior profit  leverage   allowed      paid   excess")
excess_total = 0
for y in list(s.columns)[1:]:
    prior = int(s.loc["net_income", y - 1])
    lev = float(r.loc["leverage", y - 1])
    allowed = st.permitted_distribution(prior, lev)
    paid = int(s.loc["dividends", y])
    excess = max(paid - allowed, 0)
    excess_total += excess
    print(f"{y:<7}{prior / 1e5:>13,.0f}{lev:>9.2f}x"
          f"{allowed / 1e5:>10,.0f}{paid / 1e5:>10,.0f}"
          f"{excess / 1e5:>9,.0f}")
print(f"kept in the business, 2023-2025: ${excess_total / 1e8:.2f}m")

prior = int(s.loc["net_income", 2025])
allowed = st.permitted_distribution(prior, float(r.loc["leverage",
                                                        2025]))
print(f"\n2026 allowance on 2025's profit: ${allowed / 1e8:.2f}m "
      f"(paid in 2025: ${s.loc['dividends', 2025] / 1e8:.2f}m)")
