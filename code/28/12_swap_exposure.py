# A five-year swap Fernhill sells a client who wants to fix a
# floating-rate loan: its exposure over time, and what it costs in CVA.
import json

import numpy as np

import fernhill
from ballast import securitisation as sec
from ballast.config import AS_OF, ROOT, SEED

NOTIONAL, YEARS, PATHS = 25_000_000, 5, 10_000      # dollars
con = fernhill.connect()
hist = con.execute("SELECT swap_5y_pct FROM market_rates "
                   "WHERE month <= ? ORDER BY month",
                   [AS_OF]).df()["swap_5y_pct"]
vol = float(hist.diff().std() * np.sqrt(12))
fixed = float(hist.iloc[-1])
print(f"five-year swap rate {fixed:.2f}%; its monthly moves since 2016"
      f" give\na volatility of {vol:.2f} points a year")

paths = sec.swap_rate_paths(fixed, vol, YEARS * 12, PATHS, SEED)
values = sec.swap_values(paths, fixed, YEARS, NOTIONAL)
ee, pfe = sec.exposure_profile(values, 0.95)
print(f"\nFernhill receives {fixed:.2f}% fixed on ${NOTIONAL:,} for "
      f"{YEARS} years\n{'month':>7}{'expected exposure $':>22}"
      f"{'95% PFE $':>14}")
for m in (0, 6, 12, 18, 24, 36, 48, 57, 60):
    print(f"{m:>7}{ee[m]:>22,.0f}{pfe[m]:>14,.0f}")
peak = int(ee.argmax())
print(f"peak expected exposure ${ee[peak]:,.0f} in month {peak}; "
      f"peak PFE ${pfe.max():,.0f}")

annuity = (0.25 * (1 + fixed / 400) ** -np.arange(1, 4 * YEARS + 1)
           ).sum()
print(f"\n{'counterparty':<22}{'CDS bp':>8}{'CVA $':>10}"
      f"{'bp a year':>11}")
for name in ("Cedar Oak Foods", "Elm Juniper Foods"):
    spread = con.execute("""
        SELECT cds_5y_bps FROM market_data JOIN companies
        USING (company_id) WHERE name = ? AND month = ?""",
                         [name, AS_OF]).fetchone()[0]
    c = sec.cva(ee, spread, fixed)
    print(f"{name:<22}{spread:>8.1f}{c:>10,.0f}"
          f"{c / (NOTIONAL * annuity) * 1e4:>11.2f}")

json.dump({"ee": ee.tolist(), "pfe": pfe.tolist(), "fixed": fixed,
           "notional": NOTIONAL},
          open(ROOT / "code/28/12_swap_exposure.json", "w"))
