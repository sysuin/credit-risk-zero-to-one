# Fernhill's checks before the score: two applications, then every one.
import fernhill

con = fernhill.connect()
APPS = ["A00000004", "A00137123"]

# Step 1: the test rate and the debt-to-income limit for each personal
# and car application. Affordability is tested at a standard rate
# before any price is set, and the limit moved with Fernhill's policy.
con.execute("""
    CREATE TEMP VIEW with_limits AS
    SELECT *,
        CASE product WHEN 'personal' THEN 10.9 ELSE 7.9 END
            AS test_rate,
        CASE WHEN app_date >= DATE '2022-07-01' THEN 0.50
             WHEN app_date >= DATE '2021-02-01' THEN 0.55
             WHEN app_date >= DATE '2020-04-01' THEN 0.45
             ELSE 0.50 END AS dti_limit
    FROM applications WHERE product IN ('personal', 'auto')
""")

# Step 2: the new loan's monthly payment at the test rate, with the
# payment formula from Chapter 2.
con.execute("""
    CREATE TEMP VIEW with_payment AS
    SELECT *, (amount_requested_cents / 100) * (test_rate / 1200)
              / (1 - pow(1 + test_rate / 1200,
                         -term_requested_months)) AS new_payment
    FROM with_limits
""")

# Step 3: debt payments, old and new, divided by monthly income.
con.execute("""
    CREATE TEMP VIEW checked AS
    SELECT *, (other_payments_cents / 100 + new_payment)
              / (stated_income_cents / 1200) AS dti
    FROM with_payment
""")

one = con.execute("""
    SELECT app_id, worst_status_24m, public_records, bureau_hit, age,
           stated_income_cents / 1200, other_payments_cents / 100,
           new_payment, dti, dti_limit
    FROM checked WHERE app_id IN (?, ?) ORDER BY app_id
""", APPS).fetchall()


def as_text(row):
    # One application's values, as the text printed in its column.
    (app_id, worst, records, hit, age, income, debts,
     payment, dti, limit) = row
    return [str(worst), str(records), "yes" if hit else "no",
            str(age), f"${income:,.2f}", f"${debts:,.2f}",
            f"${payment:,.2f}", f"{dti:.3f}", f"{limit:.2f}"]


labels = ["worst arrears, 24 months", "public records",
          "bureau file", "age", "monthly income",
          "existing debt payments", "new payment, test rate",
          "debt-to-income", "debt-to-income limit"]
first, second = one
print(f"{'':<26}{first[0]:>13}{second[0]:>13}")
for label, a, b in zip(labels, as_text(first), as_text(second)):
    print(f"{label:<26}{a:>13}{b:>13}")

print()
print(f"{'rule, personal and auto':<34}{'broke it':>9}{'approved':>10}")
RULES = [("arrears of 90+ days in 24 months", "worst_status_24m >= 90"),
         ("a public record", "public_records > 0"),
         ("no bureau file and under 25", "NOT bureau_hit AND age < 25"),
         ("debt-to-income over the limit", "dti > dti_limit")]
# For each rule: how many applicants broke it, and how many of those
# Fernhill approved anyway.
for label, rule in RULES:
    broke, approved = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE decision = 'approve')
        FROM checked WHERE {rule}""").fetchone()
    print(f"{label:<34}{broke:>9,}{approved:>10}")
