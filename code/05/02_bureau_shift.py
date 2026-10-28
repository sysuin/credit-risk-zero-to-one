# The bureau scores of 2019's applicants, month by month, either side
# of 1 July.
import json

import fernhill

con = fernhill.connect()
# One row per month: applicants, how many had a score, its mean and
# spread, and which version of the score the bureau sent.
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

# The same measures for the two halves of the year, side by side.
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
# halves[0] is January to June, halves[1] is July to December.
first, second = halves
names = ["mean score", "std dev", "10th percentile", "median",
         "90th percentile", "mean age"]
print()
print(f"{'':<20}{'Jan-Jun':>10}{'Jul-Dec':>10}{'change':>9}")
for i, name in enumerate(names, start=1):
    before, after = first[i], second[i]
    change = round(after - before, 1) + 0.0   # + 0.0 turns -0.0 to 0.0
    print(f"{name:<20}{before:>10.1f}{after:>10.1f}{change:>+9.1f}")
before, after = first[7] / 100, second[7] / 100
print(f"{'median income':<20}{before:>10,.0f}{after:>10,.0f}"
      f"{after - before:>+9,.0f}")
print(f"{'personal cut-off':<20}{first[8]:>10}{second[8]:>10}")

bins = con.execute("""
    SELECT app_date >= DATE '2019-07-01' AS after,
           (bureau_score // 20) * 20 AS lo, count(*)
    FROM applications
    WHERE year(app_date) = 2019 AND bureau_hit
    GROUP BY ALL ORDER BY ALL
""").fetchall()
# Count applicants in 20-point bands of score, for the figure.
out = {"before": {}, "after": {}, "mean_before": first[1],
       "mean_after": second[1]}
for after, lo, n in bins:
    out["after" if after else "before"][int(lo)] = n
with open("code/05/02_bureau_shift.json", "w") as f:
    json.dump(out, f, indent=1)
