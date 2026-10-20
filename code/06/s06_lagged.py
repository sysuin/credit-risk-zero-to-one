# Exercise 6: personal-loan write-offs over the balance two years
# earlier, beside the same-year average balance.
import fernhill
from ballast import performance as perf

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
dec = dict(con.execute("""
    SELECT year(month), sum(balance_cents) FROM performance
    WHERE product = 'personal' AND month(month) = 12
      AND status IN ('up_to_date', 'arrears', 'default')
    GROUP BY 1""").fetchall())
print(f"{'year':<6}{'written off':>13}{'avg bal':>9}{'lag 1':>8}"
      f"{'lag 2':>8}")
for y in range(2021, 2026):
    r = perf.portfolio_rates(con, "personal", y, eps)
    w = r["written_off"]
    print(f"{y:<6}{w / 100:>13,.0f}{r['charge_off_rate']:>9.2%}"
          f"{w / dec[y - 1]:>8.2%}{w / dec[y - 2]:>8.2%}")
