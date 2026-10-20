# Fernhill's loan book at a glance: what it holds, and over what span.
import fernhill

con = fernhill.connect()

rows = con.execute("""
    SELECT product,
           count(*)                                   AS applications,
           count(*) FILTER (WHERE outcome = 'booked') AS booked
    FROM applications
    GROUP BY product
    ORDER BY applications DESC
""").fetchall()
print(f"{'product':<10}{'applications':>14}{'booked':>10}{'share':>8}")
for product, apps, booked in rows:
    print(f"{product:<10}{apps:>14,}{booked:>10,}{booked / apps:>8.0%}")

total = sum(r[1] for r in rows)
print(f"{'all':<10}{total:>14,}{sum(r[2] for r in rows):>10,}")

first, last, months = con.execute("""
    SELECT min(month), max(month), count(*) FROM performance
""").fetchone()
accounts = con.execute("SELECT count(*) FROM accounts").fetchone()[0]
print()
print(f"accounts, all products:      {accounts:>10,}")
print(f"account-months of history:   {months:>10,}")
print(f"from {first} to {last}")
