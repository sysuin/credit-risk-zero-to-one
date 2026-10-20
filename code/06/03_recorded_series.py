# Fernhill's defaults table, year by year: which definition each row
# was recorded under, and what triggered it.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    SELECT year(default_month) AS yr, definition,
           count(*) AS n,
           count(*) FILTER (WHERE trigger = 'days_past_due') AS dpd,
           count(*) FILTER (WHERE trigger = 'bankruptcy') AS bk,
           count(*) FILTER (WHERE trigger = 'charged_off') AS co,
           min(default_month) AS first, max(default_month) AS last
    FROM defaults GROUP BY ALL ORDER BY yr""").fetchall()
print(f"{'year':<6}{'definition':<11}{'defaults':>9}{'90 dpd':>8}"
      f"{'bankrupt':>9}{'charged':>8}  months")
for yr, d, n, dpd, bk, co, first, last in rows:
    print(f"{yr:<6}{d:<11}{n:>9}{dpd:>8}{bk:>9}{co:>8}  "
          f"{first:%b}-{last:%b}")
