# A five-year resetting mortgage from 2018 through the rate rise.
import fernhill

con = fernhill.connect()

acc = con.execute("""
    SELECT a.account_id
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'mortgage' AND a.term_months = 300
      AND a.rate_type = 'fixed_then_variable' AND a.fixed_months = 60
      AND year(a.open_date) = 2018
    GROUP BY a.account_id, a.amount_cents
    HAVING max(p.month) >= '2024-12-31' AND max(p.missed) = 0
    ORDER BY abs(a.amount_cents - 25000000), a.account_id
    LIMIT 1
""").fetchone()[0]
opened, amount = con.execute(
    "SELECT open_date, amount_cents FROM accounts WHERE account_id = ?",
    [acc]).fetchone()
print(f"{acc}, ${amount / 100:,.0f}, opened {opened}")

rows = con.execute("""
    SELECT month, rate_pct, scheduled_cents FROM performance
    WHERE account_id = ? AND month BETWEEN '2021-12-31' AND '2024-12-31'
    ORDER BY month
""", [acc]).fetchall()
print(f"{'month':<9}{'rate':>7}{'payment':>10}")
for k, (m, rate, pay) in enumerate(rows):
    if m.month % 3 == 0 or rate != rows[k - 1][1]:
        print(f"{m:%Y-%m}  {rate:>6.2f}%{pay / 100:>10,.0f}")
print(f"change {rows[-1][2] / rows[0][2] - 1:.0%}")
