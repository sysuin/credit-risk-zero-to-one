# Chapter 1's question again: Fernhill's personal loans, 2021-2025,
# measured six ways, each against its own denominator.
import fernhill
from ballast import performance as perf

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
years = range(2021, 2026)
r = {y: perf.portfolio_rates(con, "personal", y, eps) for y in years}
sold = dict(con.execute("""
    SELECT year(r.month), sum(r.amount_cents) FROM recoveries r
    JOIN accounts a USING (account_id)
    WHERE a.product = 'personal' AND r.kind = 'debt_sale'
    GROUP BY 1""").fetchall())

print(f"{'year':<6}{'written off':>13}{'recovered':>12}"
      f"{'debt sale':>11}{'avg balance':>14}")
for y in years:
    print(f"{y:<6}{r[y]['written_off'] / 100:>13,.0f}"
          f"{r[y]['recovered'] / 100:>12,.0f}"
          f"{sold.get(y, 0) / 100:>11,.0f}"
          f"{r[y]['avg_balance'] / 100:>14,.0f}")
print(f"\n{'rates':<22}" + "".join(f"{y:>9}" for y in years))
for label, key in [("default rate", "default_rate"),
                   ("charge-off rate", "charge_off_rate"),
                   ("net loss rate", "net_loss_rate"),
                   ("30+ dpd, 31 Dec", "dq30_rate"),
                   ("90+ dpd, 31 Dec", "dq90_rate")]:
    print(f"{label:<22}" + "".join(
        f"{r[y][key]:>9.2%}" for y in years))
print(f"{'accounts at risk':<22}" + "".join(
    f"{r[y]['at_risk']:>9,}" for y in years))

young = con.execute("""
    SELECT year(p.month) + 1, sum(p.balance_cents) FILTER (
               WHERE a.open_date > p.month - INTERVAL 12 MONTH)
           / sum(p.balance_cents)
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.product = 'personal' AND month(p.month) = 12
      AND p.status IN ('up_to_date', 'arrears', 'default')
      AND year(p.month) BETWEEN 2020 AND 2024
    GROUP BY 1 ORDER BY 1""").fetchall()
print(f"{'opened in last year':<22}" + "".join(
    f"{share:>9.1%}" for _, share in young))
print("(share of the 1 January balance in loans under a year old)")
