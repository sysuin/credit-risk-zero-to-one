# Every personal loan Fernhill made in 2017, followed to 2025.
import fernhill

con = fernhill.connect()

# Three steps: pick the 2017 loans, add up each loan's monthly
# history, and add up what came back after any write-off. Then
# total the three over all the loans.
totals = con.execute("""
    WITH loans_2017 AS (
        SELECT account_id, amount_cents, close_reason
        FROM accounts
        WHERE product = 'personal' AND year(open_date) = 2017
    ),
    history AS (
        -- what was paid includes any final payoff
        SELECT p.account_id,
               sum(p.paid_cents)                         AS paid,
               sum(p.balance_cents * r.cost_of_funds_pct
                   / 100 / 12)                           AS funding,
               max((p.missed >= 3)::INT)                 AS defaulted,
               arg_max(p.balance_cents, p.month)         AS last_balance
        FROM performance p JOIN market_rates r USING (month)
        WHERE p.account_id IN (SELECT account_id FROM loans_2017)
        GROUP BY p.account_id
    ),
    came_back AS (
        SELECT account_id, sum(amount_cents) AS recovered
        FROM recoveries
        WHERE account_id IN (SELECT account_id FROM loans_2017)
        GROUP BY account_id
    )
    SELECT count(*), sum(l.amount_cents), sum(h.paid),
           coalesce(sum(c.recovered), 0),
           sum(h.funding), sum(h.defaulted),
           sum(CASE WHEN l.close_reason = 'charged_off'
                    THEN h.last_balance ELSE 0 END)
    FROM loans_2017 l JOIN history h USING (account_id)
    LEFT JOIN came_back c USING (account_id)
""").fetchone()
n, lent, received, recovered, funding, defaulted, written_off = totals


def dollars(cents):
    """Cents as whole dollars, right-aligned in 14 characters."""
    return f"{cents / 100:>14,.0f}"


print(f"loans made in 2017            {n:>10,}")
print(f"went 90 days past due         {defaulted:>10,}"
      f"  ({defaulted / n:.1%})")
print()
print(f"lent                    {dollars(lent)}")
print(f"received from borrowers {dollars(received)}")
print(f"written off             {dollars(written_off)}")
print(f"recovered afterwards    {dollars(recovered)}")
print(f"cost of funds           {dollars(funding)}")
net = received + recovered - lent - funding
print(f"left over               {dollars(net)}")
print()
loss = written_off - recovered
print(f"net credit loss         {dollars(loss)}"
      f"  ({loss / lent:.1%} of lent)")
