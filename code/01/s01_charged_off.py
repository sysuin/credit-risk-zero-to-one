# Exercise 1.1: the 2017 loans that reached 90 days past due, and
# what became of them.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    WITH loans_2017 AS (
        SELECT account_id, close_reason FROM accounts
        WHERE product = 'personal' AND year(open_date) = 2017
    ),
    went_90_days AS (
        SELECT account_id FROM performance
        WHERE missed >= 3 GROUP BY account_id
    )
    SELECT coalesce(close_reason, 'still open') AS ending, count(*)
    FROM loans_2017 JOIN went_90_days USING (account_id)
    GROUP BY ending ORDER BY count(*) DESC, ending
""").fetchall()
print(f"{'how it ended':<16}{'loans':>7}")
total = 0
for ending, n in rows:
    print(f"{ending:<16}{n:>7}")
    total = total + n
print(f"{'all':<16}{total:>7}")
