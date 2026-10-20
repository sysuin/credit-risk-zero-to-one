# Five-year CDS spreads on Fernhill's larger listed clients, and what
# a spread says about default: the hazard rate and the probability.
import numpy as np

import fernhill
from ballast import market as mk

con = fernhill.connect()
n, names, first = con.execute("""
    SELECT count(*), count(DISTINCT company_id), min(month)
    FROM market_data WHERE cds_5y_bps IS NOT NULL""").fetchone()
print(f"CDS quotes: {n:,} month ends on {names} clients, "
      f"from {first:%b %Y}")
spreads = np.array([r[0] for r in con.execute("""
    SELECT cds_5y_bps FROM market_data
    WHERE cds_5y_bps IS NOT NULL ORDER BY 1""").fetchall()])
qs = [10, 25, 50, 75, 90, 99]
print("  percentile " + "".join(f"{q:>8}" for q in qs))
print("  spread, bp " + "".join(
    f"{np.percentile(spreads, q):>8.0f}" for q in qs))

worst = con.execute("""
    SELECT c.name, max(m.cds_5y_bps), d.default_month
    FROM market_data m JOIN companies c USING (company_id)
    LEFT JOIN corporate_defaults d USING (company_id)
    GROUP BY c.name, d.default_month
    HAVING max(m.cds_5y_bps) > 2000 ORDER BY 2 DESC""").fetchall()
print("\nwidest quotes ever")
for name, bp, dm in worst:
    fate = f"defaulted {dm:%b %Y}" if dm else "no default"
    print(f"  {name:<26}{bp:>8,.0f} bp   {fate}")

print(f"\nwhat a spread implies (loss given default "
      f"{mk.CDS_LGD:.0%})")
print(f"  {'spread, bp':>10}{'hazard':>10}{'1-year PD':>11}"
      f"{'5-year PD':>11}")
for bp in (15, 50, 100, 300, 1000, 3000):
    h = mk.hazard_from_spread(bp)
    print(f"  {bp:>10,}{h:>10.2%}{mk.pd_from_hazard(h):>11.2%}"
          f"{mk.pd_from_hazard(h, 5):>11.1%}")
