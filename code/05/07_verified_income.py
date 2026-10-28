# What the check found: verified income beside stated income, for
# personal-loan applications whose income was verified.
import fernhill

con = fernhill.connect()
# Is there a verified figure exactly when the flag says verified?
missing = con.execute("""
    SELECT count(*) FILTER (WHERE income_verified
                              AND verified_income_cents IS NULL),
           count(*) FILTER (WHERE NOT income_verified
                              AND verified_income_cents IS NOT NULL)
    FROM applications
""").fetchone()
print(f"verified without a figure: {missing[0]}; "
      f"a figure without verification: {missing[1]}")
print()
print("personal loans, income verified: verified / stated income")
print(f"{'channel':<10}{'checked':>9}{'median':>9}{'lower':>9}"
      f"{'same':>8}")
# For each channel: how many were checked, the median of verified
# over stated income, and how often the check found less or the same.
checked = con.execute("""
    SELECT channel, count(*),
           median(verified_income_cents / stated_income_cents),
           avg((verified_income_cents < stated_income_cents)::INT),
           avg((verified_income_cents = stated_income_cents)::INT)
    FROM applications
    WHERE product = 'personal' AND income_verified
    GROUP BY channel ORDER BY channel
""").fetchall()
for ch, n, ratio, lower, same in checked:
    print(f"{ch:<10}{n:>9,}{ratio:>9.2f}{lower:>9.1%}{same:>8.1%}")
