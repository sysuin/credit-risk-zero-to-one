# Fernhill's checks before the score: two applications, then every one.
import fernhill

con = fernhill.connect()
APPS = ["A00000004", "A00137123"]

# Affordability is tested at a standard rate before any price is set,
# and the debt-to-income limit moved with Fernhill's policy.
CHECKS = """
WITH a AS (
    SELECT *,
        CASE product WHEN 'personal' THEN 10.9 ELSE 7.9 END
            AS test_rate,
        CASE WHEN app_date >= DATE '2022-07-01' THEN 0.50
             WHEN app_date >= DATE '2021-02-01' THEN 0.55
             WHEN app_date >= DATE '2020-04-01' THEN 0.45
             ELSE 0.50 END AS dti_limit
    FROM applications WHERE product IN ('personal', 'auto')
), b AS (
    SELECT *, (amount_requested_cents / 100) * (test_rate / 1200)
              / (1 - pow(1 + test_rate / 1200,
                         -term_requested_months)) AS new_payment
    FROM a
)
SELECT *, (other_payments_cents / 100 + new_payment)
          / (stated_income_cents / 1200) AS dti
FROM b
"""
con.execute(f"CREATE TEMP VIEW checked AS {CHECKS}")

one = con.execute("""
    SELECT app_id, worst_status_24m, public_records, bureau_hit, age,
           stated_income_cents / 1200, other_payments_cents / 100,
           new_payment, dti, dti_limit
    FROM checked WHERE app_id IN (?, ?) ORDER BY app_id
""", APPS).fetchall()
labels = ["worst arrears, 24 months", "public records",
          "bureau file", "age", "monthly income",
          "existing debt payments", "new payment, test rate",
          "debt-to-income", "debt-to-income limit"]
fmt = [str, str, lambda v: "yes" if v else "no", str,
       lambda v: f"${v:,.2f}", lambda v: f"${v:,.2f}",
       lambda v: f"${v:,.2f}", lambda v: f"{v:.3f}",
       lambda v: f"{v:.2f}"]
print(f"{'':<26}" + "".join(f"{r[0]:>13}" for r in one))
for i, (label, f) in enumerate(zip(labels, fmt)):
    print(f"{label:<26}" + "".join(f"{f(r[i + 1]):>13}" for r in one))

print()
print(f"{'rule, personal and auto':<34}{'broke it':>9}{'approved':>10}")
RULES = [("arrears of 90+ days in 24 months", "worst_status_24m >= 90"),
         ("a public record", "public_records > 0"),
         ("no bureau file and under 25", "NOT bureau_hit AND age < 25"),
         ("debt-to-income over the limit", "dti > dti_limit")]
for label, rule in RULES:
    broke, approved = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE decision = 'approve')
        FROM checked WHERE {rule}""").fetchone()
    print(f"{label:<34}{broke:>9,}{approved:>10}")
