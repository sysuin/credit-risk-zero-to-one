# What a personal loan's funding costs: the swap curve at the loan's
# expected life, and how long Fernhill's loans actually live.
import fernhill
from ballast import loanmath, pricing

con = fernhill.connect()
m = con.execute("""SELECT policy_rate_pct, cost_of_funds_pct,
                          swap_2y_pct, swap_5y_pct
                   FROM market_rates WHERE month = DATE '2025-12-31'
                """).df().iloc[0].to_dict()
print("December 2025: policy {policy_rate_pct:.2f}%, cost of funds "
      "{cost_of_funds_pct:.2f}%,\n  2-year swap {swap_2y_pct:.2f}%, "
      "5-year swap {swap_5y_pct:.2f}%".format(**m))
print("Transfer price by expected life:")
for life in (6, 12, 18, 24, 36, 60):
    print(f"  {life:>3} months  {pricing.ftp_pct(m, life):.2f}%")

life = con.execute("""
    WITH loans AS (
        SELECT account_id, amount_cents, close_reason = 'prepaid' AS pp
        FROM accounts WHERE product = 'personal' AND term_months = 36
          AND open_date BETWEEN DATE '2016-01-01'
                            AND DATE '2021-12-31')
    SELECT count(*), sum(owed) / sum(amount_cents), avg(pp::INT)
    FROM loans JOIN (SELECT account_id, sum(balance_cents) AS owed
                     FROM performance GROUP BY 1) USING (account_id)
    """).fetchone()
s = loanmath.schedule(1_200_000, 12.0, 36)
print(f"\n36-month personal loans opened 2016-2021: {life[0]:,}")
sched = s["opening"].sum() / 1_200_000
print(f"  on schedule, average life {sched:.1f} months")
print(f"  as they behaved, {life[1]:.1f} months "
      f"({life[2]:.0%} prepaid in full)")

push = con.execute("""
    WITH loans AS (
        SELECT a.account_id, a.rate_pct, a.open_date,
               m.swap_2y_pct + m.cost_of_funds_pct - m.policy_rate_pct
                   AS ftp
        FROM accounts a JOIN market_rates m
          ON m.month = last_day(a.open_date)
        WHERE a.product = 'personal'
          AND a.open_date BETWEEN DATE '2021-02-01'
                              AND DATE '2022-06-30'),
    paid AS (
        SELECT p.account_id,
               sum(p.balance_cents * r.cost_of_funds_pct)
                   / sum(p.balance_cents) AS cof
        FROM performance p JOIN market_rates r USING (month)
        WHERE p.account_id IN (SELECT account_id FROM loans)
        GROUP BY 1)
    SELECT count(*), avg(rate_pct), avg(ftp), avg(cof)
    FROM loans JOIN paid USING (account_id)""").fetchone()
print(f"\nGrowth-push loans ({push[0]:,}): rate {push[1]:.2f}%, "
      f"transfer price\n  at booking {push[2]:.2f}%, cost of funds "
      f"over their lives {push[3]:.2f}%")
