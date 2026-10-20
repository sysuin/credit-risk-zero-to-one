# Mean bureau score in each half of every year: how far two ordinary
# halves of a year differ, against the change in 2019.
import fernhill

con = fernhill.connect()
print(f"{'year':<6}{'Jan-Jun':>9}{'Jul-Dec':>9}{'change':>8}")
for y, h1, h2 in con.execute("""
    SELECT year(app_date),
           avg(bureau_score) FILTER (WHERE month(app_date) <= 6),
           avg(bureau_score) FILTER (WHERE month(app_date) > 6)
    FROM applications GROUP BY ALL ORDER BY ALL
""").fetchall():
    print(f"{y:<6}{h1:>9.1f}{h2:>9.1f}{h2 - h1:>+8.1f}")
