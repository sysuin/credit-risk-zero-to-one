# A no-hit's bureau fields look like a spotless record; how no-hits
# aged 25 and over were decided, and how their loans went.
import fernhill

con = fernhill.connect()
print(f"{'aged 25 and over':<34}{'hit':>12}{'no hit':>10}")
for label, expr in [
        ("worst status in 24 months is 0", "worst_status_24m = 0"),
        ("no enquiries in 6 months", "enquiries_6m = 0"),
        ("no public records", "public_records = 0"),
        ("approved", "decision = 'approve'")]:
    hit, nohit = con.execute(f"""
        SELECT avg(({expr})::INT) FILTER (WHERE bureau_hit),
               avg(({expr})::INT) FILTER (WHERE NOT bureau_hit)
        FROM applications WHERE age >= 25
    """).fetchone()
    print(f"{label:<34}{hit:>12.1%}{nohit:>10.1%}")

# Booked personal and car loans opened before 2025, so every one has
# had twelve months to show how it is going. "Bad" here means three
# payments missed (90 days past due) within twelve months of opening.
for hit, n, bad in con.execute("""
    WITH first_year AS (
        SELECT p.account_id, max(p.missed) >= 3 AS bad
        FROM performance p JOIN accounts c USING (account_id)
        WHERE p.month <= last_day(c.open_date + INTERVAL 12 MONTH)
        GROUP BY p.account_id)
    SELECT a.bureau_hit, count(*), avg(f.bad::INT)
    FROM applications a JOIN first_year f USING (account_id)
    WHERE a.age >= 25 AND a.product IN ('personal', 'auto')
      AND a.app_date < DATE '2025-01-01'
    GROUP BY a.bureau_hit ORDER BY a.bureau_hit DESC
""").fetchall():
    label = "hit" if hit else "no hit"
    print(f"booked loans, {label:<7}{n:>8,}   bad in first year "
          f"{bad:>6.1%}")
