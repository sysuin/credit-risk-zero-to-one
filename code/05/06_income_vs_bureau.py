# Stated income set against two things the bureau reports and the
# applicant did not write: revolving limits and other monthly payments.
import json

import fernhill

con = fernhill.connect()
# A view p of personal-loan applications on score version 3, with
# three new columns: the 50-point score band, stated income divided
# by the revolving limit, and other payments as a share of income.
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


def table(title, expr, fmt, where="TRUE", gap=True):
    """Print expr for each channel in three score bands. If gap is
    True, add how far brokers are above branches."""
    print(title)
    header = f"{'score':<10}{'branch':>9}{'online':>9}{'broker':>9}"
    if gap:
        header += f"{'broker vs branch':>18}"
    print(header)
    for lo in (550, 600, 650):
        rows = con.execute(f"""
            SELECT channel, {expr} FROM p
            WHERE band = {lo} AND {where}
            GROUP BY channel""").fetchall()
        by_channel = dict(rows)
        branch = by_channel["branch"]
        online = by_channel["online"]
        broker = by_channel["broker"]
        line = (f"{lo}-{lo + 49:<6}{branch:>9{fmt}}"
                f"{online:>9{fmt}}{broker:>9{fmt}}")
        if gap:
            line += f"{broker / branch - 1:>+18.0%}"
        print(line)


table("stated income / revolving limit (median)",
      "median(to_limit)", ".2f")
table("other payments / stated income (median, no mortgage)",
      "median(to_pay)", ".1%", where="housing <> 'mortgage'")
table("applications", "count(*)", ",", gap=False)
table("mean bureau score", "avg(bureau_score)", ".1f", gap=False)

print()
print("550-699: stated income / revolving limit (median)")
groups = [
    ("broker, unverified",
     "channel = 'broker' AND NOT income_verified"),
    ("broker, verified", "channel = 'broker' AND income_verified"),
    ("broker, to Jun 2022",
     "channel = 'broker' AND app_date < '2022-07-01'"),
    ("broker, from Jul 2022",
     "channel = 'broker' AND app_date >= '2022-07-01'"),
    ("branch, from Jul 2022",
     "channel = 'branch' AND app_date >= '2022-07-01'"),
]
for label, cond in groups:
    n, r = con.execute(f"""
        SELECT count(*), median(to_limit) FROM p
        WHERE band BETWEEN 550 AND 650 AND {cond}""").fetchone()
    print(f"  {label:<24}{n:>7,}{r:>8.2f}")

# Save the ratio for every band and channel, for the figure.
bands = con.execute("""
    SELECT band, channel, count(*), median(to_limit) FROM p
    WHERE band BETWEEN 450 AND 750 GROUP BY ALL ORDER BY ALL
""").fetchall()
records = []
for band, channel, n, ratio in bands:
    records.append({"band": int(band), "channel": channel, "n": n,
                    "ratio": ratio})
with open("code/05/06_income_vs_bureau.json", "w") as f:
    json.dump(records, f, indent=1)
