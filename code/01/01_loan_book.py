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
# One line per product, adding up the totals as we go.
print(f"{'product':<10}{'applications':>14}{'booked':>10}{'share':>8}")
all_apps = 0
all_booked = 0
for product, apps, booked in rows:
    print(f"{product:<10}{apps:>14,}{booked:>10,}{booked / apps:>8.0%}")
    all_apps = all_apps + apps
    all_booked = all_booked + booked
print(f"{'all':<10}{all_apps:>14,}{all_booked:>10,}")

# The span of the monthly history, and how many accounts it covers.
first, last, months = con.execute("""
    SELECT min(month), max(month), count(*) FROM performance
""").fetchone()
accounts = con.execute("SELECT count(*) FROM accounts").fetchone()[0]
print()
print(f"accounts, all products:      {accounts:>10,}")
print(f"account-months of history:   {months:>10,}")
print(f"from {first} to {last}")
