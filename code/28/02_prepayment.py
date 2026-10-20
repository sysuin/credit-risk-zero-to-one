# How fast Fernhill's car loans prepay: the monthly rate (SMM) and
# its annual equivalent (CPR), by age and by calendar year.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
curve = sec.prepayment_curve(con)
years = con.execute("""
    WITH p AS (
        SELECT month, status,
               lag(status) OVER w AS prev,
               lag(missed) OVER w AS prev_missed
        FROM performance WHERE product = 'auto'
        WINDOW w AS (PARTITION BY account_id ORDER BY month))
    SELECT year(month) AS yr, count(*) AS at_risk,
           count(*) FILTER (WHERE status = 'prepaid') AS prepaid
    FROM p
    WHERE prev IN ('up_to_date', 'arrears') AND prev_missed < 3
    GROUP BY 1 ORDER BY 1""").fetchall()

print(f"{'age (months)':<14}{'at risk':>9}{'SMM':>8}{'CPR':>7}"
      f"{'':6}{'year':<6}{'CPR':>7}")
left = [(f"{b}-{b + sec.PREPAY_BAND - 1}", int(r.at_risk), r.smm,
         r.cpr) for b, r in curve.iterrows()]
for i in range(max(len(left), len(years))):
    a = (f"{left[i][0]:<14}{left[i][1]:>9,}{left[i][2]:>8.2%}"
         f"{left[i][3]:>7.1%}" if i < len(left) else " " * 38)
    b = ""
    if i < len(years):
        yr, n, k = years[i]
        b = f"{'':6}{yr:<6}{1 - (1 - k / n) ** 12:>7.1%}"
    print(a + b)
all_n, all_k = curve["at_risk"].sum(), curve["prepaid"].sum()
print(f"\nall ages: {all_k:,} prepayments in {all_n:,} loan-months, "
      f"CPR {1 - (1 - all_k / all_n) ** 12:.1%}")
