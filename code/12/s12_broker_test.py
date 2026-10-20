# Exercise 12.3: how big a repeat price test must be to tell whether
# brokers' customers respond to price differently from the rest.
import sys

import fernhill
from scipy.stats import norm

from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import scored  # noqa: E402

z = norm.ppf(0.975) + norm.ppf(0.80)
direct = (0.74, 0.555)       # branch and online, -1.5 and +1.5 arms
broker = (0.70, 0.45)        # brokers if their gap were 25 points
gap = (broker[0] - broker[1]) - (direct[0] - direct[1])
var_broker = sum(p * (1 - p) for p in broker)
var_direct = sum(p * (1 - p) for p in direct)
# Branch and online applicants are about six to one in the test, so
# their arms are six times as large as the brokers'.
n = z ** 2 * (var_broker + var_direct / 6) / gap ** 2
print(f"Difference in gaps to detect: {100 * gap:.1f} points")
print(f"Broker applicants needed in each arm: {n:,.0f}")

con = fernhill.connect()
a = scored(con)
y = a[a["decision"].eq("approve") & a["app_date"].dt.year.eq(2025)]
per_month = y["channel"].eq("broker").sum() / 12
arm = per_month * 0.10 / 2
print(f"Broker approvals a month in 2025: {per_month:.0f}; at one in "
      f"ten, {arm:.1f} an arm")
print(f"Months to gather them: {n / arm:.0f}")
