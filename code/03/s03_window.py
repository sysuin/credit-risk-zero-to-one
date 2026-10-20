# Loss frequency by product within one, two and three years of opening.
import fernhill

con = fernhill.connect()

rows = con.execute("""
    WITH fam AS (
        SELECT account_id,
               coalesce(predecessor_id, account_id) AS family
        FROM accounts
    ),
    f AS (
        SELECT fam.family, min(a.open_date) AS opened,
               any_value(a.product) AS product
        FROM accounts a JOIN fam USING (account_id)
        GROUP BY fam.family
    ),
    hit AS (
        SELECT fam.family, min(p.month) AS first90
        FROM performance p JOIN fam USING (account_id)
        WHERE p.missed >= 3
        GROUP BY fam.family
    ),
    m AS (
        SELECT f.product,
               coalesce(date_diff('month', f.opened, h.first90), 999)
                   AS months
        FROM f LEFT JOIN hit h USING (family)
        WHERE year(f.opened) BETWEEN 2016 AND 2022
    )
    SELECT product, avg((months <= 12)::INT), avg((months <= 24)::INT),
           avg((months <= 36)::INT)
    FROM m GROUP BY product ORDER BY product
""").fetchall()
print(f"{'product':<15}{'1 year':>8}{'2 years':>9}{'3 years':>9}"
      f"{'1y / 3y':>9}")
for p, y1, y2, y3 in rows:
    print(f"{p:<15}{y1:>8.1%}{y2:>9.1%}{y3:>9.1%}{y1 / y3:>9.0%}")
