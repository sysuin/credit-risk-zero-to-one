# Every personal loan Fernhill made in 2017, followed to 2025.
import fernhill

con = fernhill.connect()

(n, lent, paid, recovered, funding,
 defaulted, written_off) = con.execute("""
    WITH v AS (
        SELECT account_id, amount_cents, close_reason
        FROM accounts
        WHERE product = 'personal' AND year(open_date) = 2017
    ),
    perf AS (
        -- what was paid includes any final payoff
        SELECT p.account_id,
               sum(p.paid_cents)                         AS paid,
               sum(p.balance_cents * r.cost_of_funds_pct
                   / 100 / 12)                           AS funding,
               max((p.missed >= 3)::INT)                 AS defaulted,
               arg_max(p.balance_cents, p.month)         AS last_balance
        FROM performance p JOIN market_rates r USING (month)
        WHERE p.account_id IN (SELECT account_id FROM v)
        GROUP BY p.account_id
    ),
    rec AS (
        SELECT account_id, sum(amount_cents) AS recovered
        FROM recoveries
        WHERE account_id IN (SELECT account_id FROM v)
        GROUP BY account_id
    )
    SELECT count(*), sum(v.amount_cents), sum(perf.paid),
           coalesce(sum(rec.recovered), 0),
           sum(perf.funding), sum(perf.defaulted),
           sum(CASE WHEN v.close_reason = 'charged_off'
                    THEN perf.last_balance ELSE 0 END)
    FROM v JOIN perf USING (account_id)
    LEFT JOIN rec USING (account_id)
""").fetchone()

received = paid
d = lambda cents: f"{cents / 100:>14,.0f}"  # noqa: E731
print(f"loans made in 2017            {n:>10,}")
print(f"went 90 days past due         {defaulted:>10,}"
      f"  ({defaulted / n:.1%})")
print()
print(f"lent                    {d(lent)}")
print(f"received from borrowers {d(received)}")
print(f"written off             {d(written_off)}")
print(f"recovered afterwards    {d(recovered)}")
print(f"cost of funds           {d(funding)}")
net = received + recovered - lent - funding
print(f"left over               {d(net)}")
print()
loss = written_off - recovered
print(f"net credit loss         {d(loss)}  ({loss / lent:.1%} of lent)")
