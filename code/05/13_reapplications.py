# Duplicates and re-applications: the keys are unique, but is anyone
# in the applications table twice?
import fernhill

con = fernhill.connect()
for label, sql in [
        ("applications", "SELECT count(*), count(DISTINCT app_id) "
                         "FROM applications"),
        ("accounts", "SELECT count(*), count(DISTINCT account_id) "
                     "FROM accounts"),
        ("account-months", "SELECT count(*), count(DISTINCT "
                           "(account_id, month)) FROM performance")]:
    rows, keys = con.execute(sql).fetchone()
    print(f"{label:<16}{rows:>11,} rows {keys:>11,} distinct keys")

# No customer number, so look for the same person by what they told
# us: pairs of applications within 90 days that agree on six answers.
con.execute("""
    CREATE TEMP TABLE pairs AS
    SELECT b.address_months - a.address_months AS moved
    FROM applications a JOIN applications b
      ON a.age = b.age AND a.region = b.region
     AND a.stated_income_cents = b.stated_income_cents
     AND a.employment = b.employment AND a.housing = b.housing
     AND a.dependants = b.dependants
     AND b.app_date BETWEEN a.app_date AND a.app_date + 90
     AND a.app_id < b.app_id
""")
total, ahead, behind = con.execute("""
    SELECT count(*),
           count(*) FILTER (WHERE moved BETWEEN 0 AND 3),
           count(*) FILTER (WHERE moved BETWEEN -4 AND -1)
    FROM pairs
""").fetchone()
print()
print("pairs agreeing on age, region, income, employment,")
print(f"housing and dependants, within 90 days:      {total:>6,}")
print(f"  months at address 0 to 3 higher the second time "
      f"{ahead:>4,}")
print(f"  months at address 1 to 4 lower (impossible) "
      f"{behind:>8,}")
