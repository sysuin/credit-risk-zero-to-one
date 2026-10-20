# Car loans that reached four missed payments: how many lost the car.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    WITH reached AS (
        SELECT DISTINCT account_id FROM performance
        WHERE product = 'auto' AND missed >= 4)
    SELECT coalesce(close_reason, 'still open'), count(*)
    FROM reached JOIN accounts USING (account_id)
    GROUP BY ALL ORDER BY count(*) DESC
""").fetchall()
total = sum(n for _, n in rows)
for reason, n in rows:
    print(f"{reason:<22}{n:>6,}{n / total:>8.1%}")
print(f"{'reached 4 missed':<22}{total:>6,}")
