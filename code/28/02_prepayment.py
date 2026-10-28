# How fast Fernhill's car loans prepay: the monthly rate (SMM) and
# its annual equivalent (CPR), by age and by calendar year.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
curve = sec.prepayment_curve(con)
# Each calendar year: loan-months open and paying, and how many of
# them ended with the loan paid off early.
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
# Age bands on the left, calendar years on the right.
ages = list(curve.iterrows())
for i in range(max(len(ages), len(years))):
    text = " " * 38
    if i < len(ages):
        start, r = ages[i]
        band = f"{start}-{start + sec.PREPAY_BAND - 1}"
        text = (f"{band:<14}{int(r.at_risk):>9,}{r.smm:>8.2%}"
                f"{r.cpr:>7.1%}")
    if i < len(years):
        yr, n, k = years[i]
        text += f"{'':6}{yr:<6}{1 - (1 - k / n) ** 12:>7.1%}"
    print(text)
all_n, all_k = curve["at_risk"].sum(), curve["prepaid"].sum()
print(f"\nall ages: {all_k:,} prepayments in {all_n:,} loan-months, "
      f"CPR {1 - (1 - all_k / all_n) ** 12:.1%}")
