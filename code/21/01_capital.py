# Fernhill's capital at each year end, by tier, and the RWA for the
# risks that are not credit risk, as its finance team records them.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    SELECT year(year_end), cet1_cents, at1_cents, tier2_cents,
           operational_rwa_cents, market_rwa_cents
    FROM bank_capital ORDER BY year_end""").fetchall()
print(f"{'$m':<6}{'CET1':>8}{'AT1':>7}{'Tier 2':>8}{'total':>8}"
      f"{'CET1 share':>11}{'op RWA':>9}{'mkt RWA':>9}")
for y, c, a, t, op, mk in rows:
    tot = c + a + t
    print(f"{y:<6}{c / 1e8:>8,.0f}{a / 1e8:>7,.0f}{t / 1e8:>8,.0f}"
          f"{tot / 1e8:>8,.0f}{c / tot:>11.1%}{op / 1e8:>9,.0f}"
          f"{mk / 1e8:>9,.0f}")
y, c, a, t, op, mk = rows[-1]
print(f"\n31 Dec {y}: CET1 ${c / 100:,.0f}, AT1 ${a / 100:,.0f},")
print(f"Tier 2 ${t / 100:,.0f}; operational RWA ${op / 100:,.0f},")
print(f"market RWA ${mk / 100:,.0f}")
