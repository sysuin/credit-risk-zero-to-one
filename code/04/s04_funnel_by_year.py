# The personal-loan funnel, year by year.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    SELECT year(app_date), count(*),
           avg((decision = 'approve')::INT),
           avg((outcome = 'booked')::INT)
    FROM applications WHERE product = 'personal'
    GROUP BY ALL ORDER BY ALL
""").fetchall()
print(f"{'year':<6}{'applied':>9}{'approved':>10}{'booked':>8}")
for year, n, approved, booked in rows:
    print(f"{year:<6}{n:>9,}{approved:>10.1%}{booked:>8.1%}")
