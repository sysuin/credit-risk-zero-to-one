# Exercise 1.1: the 2017 loans that reached 90 days past due, and
# what became of them.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    WITH v AS (SELECT account_id, close_reason FROM accounts
               WHERE product = 'personal' AND year(open_date) = 2017),
    d AS (SELECT account_id FROM performance
          WHERE missed >= 3 GROUP BY account_id)
    SELECT coalesce(v.close_reason, 'still open') AS ending, count(*)
    FROM v JOIN d USING (account_id)
    GROUP BY ending ORDER BY count(*) DESC, ending
""").fetchall()
print(f"{'how it ended':<16}{'loans':>7}")
for ending, n in rows:
    print(f"{ending:<16}{n:>7}")
print(f"{'all':<16}{sum(n for _, n in rows):>7}")
