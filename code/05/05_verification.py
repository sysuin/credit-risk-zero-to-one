# Which applications had their income verified, and the naive
# comparison of verified with unverified stated incomes.
import fernhill

con = fernhill.connect()
# Fernhill's four rules for verifying income, written as SQL.
groups = [
    ("mortgages", "product = 'mortgage'"),
    ("asked for over $15,000", "amount_requested_cents > 1500000"),
    ("consented to open banking", "ob_consent"),
    ("broker or dealer, from Jul 2022",
     "channel IN ('broker', 'dealer') AND app_date >= '2022-07-01'"),
]
print(f"{'applications':<34}{'count':>9}{'verified':>10}")
rules_seen = []
for label, rule in groups:
    n, v = con.execute(f"""
        SELECT count(*), avg(income_verified::INT)
        FROM applications WHERE {rule}
    """).fetchone()
    print(f"{label:<34}{n:>9,}{v:>10.1%}")
    rules_seen.append(f"({rule})")
# The applications that none of the four rules covers.
any_rule = " OR ".join(rules_seen)
n, v = con.execute(f"""
    SELECT count(*), avg(income_verified::INT)
    FROM applications WHERE NOT ({any_rule})
""").fetchone()
print(f"{'none of these':<34}{n:>9,}{v:>10.1%}")

print()
print("personal loans: median stated income")
print(f"{'channel':<10}{'unverified':>12}{'verified':>12}{'ratio':>8}")
medians = con.execute("""
    SELECT channel,
           median(stated_income_cents)
               FILTER (WHERE NOT income_verified),
           median(stated_income_cents)
               FILTER (WHERE income_verified)
    FROM applications WHERE product = 'personal'
    GROUP BY channel ORDER BY channel
""").fetchall()
for ch, unv, ver in medians:
    print(f"{ch:<10}{unv / 100:>12,.0f}{ver / 100:>12,.0f}"
          f"{ver / unv:>8.2f}")
