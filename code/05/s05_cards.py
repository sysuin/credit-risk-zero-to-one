# Stated income against revolving limits for card applications, by
# channel within score bands: the personal-loan comparison repeated.
import fernhill

con = fernhill.connect()
print("card applications, version 3, revolving limit known")
print(f"{'score':<10}{'branch':>9}{'online':>9}{'broker':>9}"
      f"{'broker vs branch':>18}")
for lo in (550, 600, 650):
    got = dict(con.execute(f"""
        SELECT channel, median(stated_income_cents
               / (revolving_balance_cents / revolving_utilisation))
        FROM applications
        WHERE product = 'card' AND bureau_version = 'v3'
          AND revolving_utilisation >= 0.05
          AND bureau_score BETWEEN {lo} AND {lo + 49}
        GROUP BY channel""").fetchall())
    b, o, k = got["branch"], got["online"], got["broker"]
    print(f"{lo}-{lo + 49:<6}{b:>9.2f}{o:>9.2f}{k:>9.2f}"
          f"{k / b - 1:>+18.0%}")
