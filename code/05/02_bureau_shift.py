# The bureau scores of 2019's applicants, month by month, either side
# of 1 July.
import json

import fernhill

con = fernhill.connect()
months = con.execute("""
    SELECT strftime(app_date, '%Y-%m') AS month,
           count(*), count(bureau_score),
           avg(bureau_score), stddev_samp(bureau_score),
           string_agg(DISTINCT bureau_version, ',')
    FROM applications
    WHERE year(app_date) = 2019
    GROUP BY month ORDER BY month
""").fetchall()
print(f"{'month':<9}{'applicants':>11}{'scored':>8}{'mean':>8}"
      f"{'std dev':>9}  version")
for m, n, scored, mean, sd, ver in months:
    print(f"{m:<9}{n:>11,}{scored:>8,}{mean:>8.1f}{sd:>9.1f}  {ver}")

halves = con.execute("""
    SELECT app_date >= DATE '2019-07-01' AS after,
           avg(bureau_score), stddev_samp(bureau_score),
           quantile_cont(bureau_score, 0.1),
           quantile_cont(bureau_score, 0.5),
           quantile_cont(bureau_score, 0.9),
           avg(age), median(stated_income_cents),
           string_agg(DISTINCT cutoff::VARCHAR, ',')
               FILTER (WHERE product = 'personal')
    FROM applications
    WHERE year(app_date) = 2019
    GROUP BY after ORDER BY after
""").fetchall()
names = ["mean score", "std dev", "10th percentile", "median",
         "90th percentile", "mean age"]
print()
print(f"{'':<20}{'Jan-Jun':>10}{'Jul-Dec':>10}{'change':>9}")
for i, name in enumerate(names, start=1):
    b, a = halves[0][i], halves[1][i]
    change = round(a - b, 1) + 0.0        # + 0.0 turns -0.0 into 0.0
    print(f"{name:<20}{b:>10.1f}{a:>10.1f}{change:>+9.1f}")
b, a = halves[0][7] / 100, halves[1][7] / 100
print(f"{'median income':<20}{b:>10,.0f}{a:>10,.0f}{a - b:>+9,.0f}")
print(f"{'personal cut-off':<20}{halves[0][8]:>10}{halves[1][8]:>10}")

bins = con.execute("""
    SELECT app_date >= DATE '2019-07-01' AS after,
           (bureau_score // 20) * 20 AS lo, count(*)
    FROM applications
    WHERE year(app_date) = 2019 AND bureau_hit
    GROUP BY ALL ORDER BY ALL
""").fetchall()
out = {"before": {}, "after": {}, "mean_before": halves[0][1],
       "mean_after": halves[1][1]}
for after, lo, n in bins:
    out["after" if after else "before"][int(lo)] = n
with open("code/05/02_bureau_shift.json", "w") as f:
    json.dump(out, f, indent=1)
