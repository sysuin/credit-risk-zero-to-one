# Who says yes to open banking: consenters and refusers compared, among
# applicants who were asked.
import fernhill

con = fernhill.connect()
# The applications that were offered open banking, as SQL.
asked = """((channel = 'online' AND app_date >= DATE '2021-03-01')
         OR (channel = 'branch' AND app_date >= DATE '2023-01-01'))"""
print(f"{'asked, and':<14}{'apps':>8}{'score':>8}{'no hit':>8}"
      f"{'age':>6}{'approved':>10}")
groups = con.execute(f"""
    SELECT ob_consent, count(*), avg(bureau_score),
           avg((NOT bureau_hit)::INT), avg(age),
           avg((decision = 'approve')::INT)
    FROM applications WHERE {asked}
    GROUP BY ob_consent ORDER BY ob_consent DESC
""").fetchall()
for consent, n, score, nohit, age, approved in groups:
    label = "said yes" if consent else "said no"
    print(f"{label:<14}{n:>8,}{score:>8.1f}{nohit:>8.1%}{age:>6.1f}"
          f"{approved:>10.1%}")

print()
print("booked personal loans asked before 2025: bad in first year")
# As in the no-hit listing: was each loan three payments behind in
# its first twelve months? Then the share, for yes and for no.
outcomes = con.execute(f"""
    WITH first_year AS (
        SELECT p.account_id, max(p.missed) >= 3 AS bad
        FROM performance p JOIN accounts c USING (account_id)
        WHERE p.month <= last_day(c.open_date + INTERVAL 12 MONTH)
        GROUP BY p.account_id)
    SELECT a.ob_consent, count(*), avg(f.bad::INT)
    FROM applications a JOIN first_year f USING (account_id)
    WHERE {asked} AND a.product = 'personal'
      AND a.app_date < DATE '2025-01-01'
    GROUP BY a.ob_consent ORDER BY a.ob_consent DESC
""").fetchall()
for consent, n, bad in outcomes:
    label = "said yes" if consent else "said no"
    print(f"  {label:<12}{n:>7,} loans{bad:>8.1%}")
