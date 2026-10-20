# Stated income set against two things the bureau reports and the
# applicant did not write: revolving limits and other monthly payments.
import json

import fernhill

con = fernhill.connect()
con.execute("""
    CREATE TEMP VIEW p AS
    SELECT *, (bureau_score // 50) * 50 AS band,
           stated_income_cents
             / (revolving_balance_cents / revolving_utilisation)
             AS to_limit,
           other_payments_cents * 12.0 / stated_income_cents AS to_pay
    FROM applications
    WHERE product = 'personal' AND bureau_version = 'v3'
      AND revolving_utilisation >= 0.05
""")
CH = ["branch", "online", "broker"]


def table(title, expr, fmt, where="TRUE", gap=True):
    print(title)
    print(f"{'score':<10}{'branch':>9}{'online':>9}{'broker':>9}"
          + (f"{'broker vs branch':>18}" if gap else ""))
    for lo in (550, 600, 650):
        got = dict(con.execute(f"""
            SELECT channel, {expr} FROM p
            WHERE band = {lo} AND {where}
            GROUP BY channel""").fetchall())
        b, o, k = (got[c] for c in CH)
        line = f"{lo}-{lo + 49:<6}" + "".join(
            f"{v:>9{fmt}}" for v in (b, o, k))
        print(line + (f"{k / b - 1:>+18.0%}" if gap else ""))


table("stated income / revolving limit (median)",
      "median(to_limit)", ".2f")
table("other payments / stated income (median, no mortgage)",
      "median(to_pay)", ".1%", where="housing <> 'mortgage'")
table("applications", "count(*)", ",", gap=False)
table("mean bureau score", "avg(bureau_score)", ".1f", gap=False)

print()
print("550-699: stated income / revolving limit (median)")
for label, cond in [
        ("broker, unverified",
         "channel = 'broker' AND NOT income_verified"),
        ("broker, verified", "channel = 'broker' AND income_verified"),
        ("broker, to Jun 2022",
         "channel = 'broker' AND app_date < '2022-07-01'"),
        ("broker, from Jul 2022",
         "channel = 'broker' AND app_date >= '2022-07-01'"),
        ("branch, from Jul 2022",
         "channel = 'branch' AND app_date >= '2022-07-01'")]:
    n, r = con.execute(f"""
        SELECT count(*), median(to_limit) FROM p
        WHERE band BETWEEN 550 AND 650 AND {cond}""").fetchone()
    print(f"  {label:<24}{n:>7,}{r:>8.2f}")

bands = con.execute("""
    SELECT band, channel, count(*), median(to_limit) FROM p
    WHERE band BETWEEN 450 AND 750 GROUP BY ALL ORDER BY ALL
""").fetchall()
with open("code/05/06_income_vs_bureau.json", "w") as f:
    json.dump([{"band": int(b), "channel": c, "n": n, "ratio": r}
               for b, c, n, r in bands], f, indent=1)
