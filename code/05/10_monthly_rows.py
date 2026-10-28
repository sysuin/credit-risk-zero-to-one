# The performance table: one personal loan from 2023, month by month,
# around the only time it fell behind, and the month it ended.
import fernhill

con = fernhill.connect()
# The first personal loan opened in early 2023 that fell two
# payments behind and had caught up by its last month.
account = con.execute("""
    SELECT account_id FROM performance
    WHERE product = 'personal' AND account_id IN (
        SELECT account_id FROM accounts
        WHERE open_date >= DATE '2023-01-01'
          AND open_date < DATE '2023-07-01')
    GROUP BY account_id
    HAVING max(missed) = 2 AND arg_max(missed, month) = 0
    ORDER BY account_id LIMIT 1
""").fetchone()[0]
amount, opened, rate, term = con.execute("""
    SELECT amount_cents, open_date, rate_pct, term_months
    FROM accounts WHERE account_id = ?""", [account]).fetchone()
print(f"{account}: ${amount / 100:,.0f} at {rate}% over {term:.0f} "
      f"months, opened {opened}")
rows = con.execute("""
    SELECT month, balance_cents, scheduled_cents, paid_cents,
           arrears_cents, missed, days_past_due, status
    FROM performance WHERE account_id = ? ORDER BY month""",
                   [account]).fetchall()
# The row numbers of the months it was behind (row[5] is missed).
behind = []
for i, row in enumerate(rows):
    if row[5] > 0:
        behind.append(i)
# Show the first two months, the last, and two months either side
# of the trouble. Count the months in between instead.
show = {0, 1, len(rows) - 1}
show.update(range(behind[0] - 2, behind[-1] + 3))
print(f"{'month':<11}{'balance':>10}{'due':>9}{'paid':>9}{'arrears':>9}"
      f"{'mis':>4}{'dpd':>4}  status")
hidden = 0
for i, (m, bal, due, paid, arr, mis, dpd, st) in enumerate(rows):
    if i not in show:
        hidden += 1
        continue
    if hidden > 0:
        print(f"{'...':<11}{hidden} months up to date")
        hidden = 0
    print(f"{m!s:<11}{bal / 100:>10,.2f}{due / 100:>9,.2f}"
          f"{paid / 100:>9,.2f}{arr / 100:>9,.2f}{mis:>4}{dpd:>4}"
          f"  {st}")
n, months = con.execute("""
    SELECT count(DISTINCT account_id), count(*) FROM performance
""").fetchone()
print(f"the whole table: {months:,} rows like these, "
      f"for {n:,} accounts")
