# Where Fernhill's applications came from, by year and by product.
import fernhill

con = fernhill.connect()
CHANNELS = ["branch", "online", "broker", "dealer"]

rows = con.execute("""
    SELECT year(app_date) AS year, channel, count(*) AS n
    FROM applications GROUP BY ALL ORDER BY year, channel
""").fetchall()
# by_year[2016]["branch"] is the number of branch applications in 2016.
by_year = {}
for year, channel, n in rows:
    if year not in by_year:
        by_year[year] = {}
    by_year[year][channel] = n

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
# table["auto"]["dealer"] is the number of car loans from dealers.
table = {}
for product, channel, n in mix:
    if product not in table:
        table[product] = {}
    table[product][channel] = n
print(f"{'product':<10}" + "".join(f"{c:>9}" for c in CHANNELS))
for product, counts in table.items():
    # A dash where a product never came through a channel.
    cells = ""
    for c in CHANNELS:
        if c in counts:
            cells += f"{counts[c]:>9,}"
        else:
            cells += f"{'-':>9}"
    print(f"{product:<10}{cells}")
