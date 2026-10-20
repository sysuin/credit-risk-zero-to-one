# Merton's model for one company in one month: Alder Oak Materials at
# the end of September and October 2020, first with a shortcut, then
# by solving the two equations.
import datetime as dt

import fernhill
from ballast import market as mk

con = fernhill.connect()
cid = con.execute("SELECT company_id FROM companies "
                  "WHERE name = 'Alder Oak Materials'").fetchone()[0]
m = mk.market_months(con)
dp = mk.default_points(con)
D = dp[(dp.company_id == cid) & (dp.fiscal_year == 2019)] \
    .default_point.iloc[0] / 100
r_free = mk.risk_free(con)

for i, day in enumerate((dt.date(2020, 9, 30),
                         dt.date(2020, 10, 31))):
    if i:
        print()
    row = m[(m.company_id == cid) & (m.month == day)].iloc[0]
    E, sE, r = row.equity / 100, row.sigma_e, r_free[day]
    print(f"{day:%d %b %Y}: equity ${E / 1e6:.2f}m, equity vol "
          f"{sE:.1%},\n  default point ${D / 1e6:.2f}m, risk-free "
          f"rate {r:.2%}")
    # The shortcut: assets = equity + debt, volatility scaled down.
    V0, s0 = E + D, sE * E / (E + D)
    # Merton: solve both equations together.
    V, s, ok = mk.solve_assets(E, sE, D, r)
    print(f"  {'$m':<10}{'assets':>8}{'vol':>8}{'gives E':>9}"
          f"{'and vol':>9}{'DD':>7}{'PD':>8}")
    for label, a, sa in (("shortcut", V0, s0), ("solved", V, s)):
        e, se = mk.equity_value(a, sa, D, r)
        dd = mk.distance_to_default(a, sa, D, r)
        print(f"  {label:<10}{a / 1e6:>8.2f}{sa:>8.1%}{e / 1e6:>9.2f}"
              f"{se:>9.1%}{dd:>7.2f}"
              f"{mk.default_probability(dd):>8.1%}")
    print(f"  solver converged: {ok}")
