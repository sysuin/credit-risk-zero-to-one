# Where Fernhill's applications came from, by year and by product.
import fernhill

con = fernhill.connect()
CHANNELS = ["branch", "online", "broker", "dealer"]

rows = con.execute("""
    SELECT year(app_date) AS year, channel, count(*) AS n
    FROM applications GROUP BY ALL ORDER BY year, channel
""").fetchall()
by_year = {}
for year, channel, n in rows:
    by_year.setdefault(year, {})[channel] = n

print(f"{'year':<6}" + "".join(f"{c:>9}" for c in CHANNELS)
      + f"{'total':>9}{'online':>9}")
for year, counts in by_year.items():
    total = sum(counts.values())
    cells = "".join(f"{counts.get(c, 0):>9,}" for c in CHANNELS)
    online = counts["online"] / total
    print(f"{year:<6}{cells}{total:>9,}{online:>9.0%}")

print()
mix = con.execute("""
    SELECT product, channel, count(*) FROM applications
    GROUP BY ALL ORDER BY product, channel
""").fetchall()
table = {}
for product, channel, n in mix:
    table.setdefault(product, {})[channel] = n
print(f"{'product':<10}" + "".join(f"{c:>9}" for c in CHANNELS))
for product, counts in table.items():
    cells = "".join(f"{counts[c]:>9,}" if c in counts else f"{'-':>9}"
                    for c in CHANNELS)
    print(f"{product:<10}{cells}")
