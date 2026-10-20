# Exercise 5: emergency loans' bad flag on the default clock: in
# default within 12 months of the month before the first payment due.
import fernhill
from ballast import performance as perf

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
for clock in ("open", "due"):
    acc = perf.cohort_accounts(con, "sme_emergency", eps, clock=clock)
    bad = acc["default_mob"] <= 12
    print(f"clock from {clock}: {len(acc):,} loans, "
          f"{int(bad.sum()):,} bad, {bad.mean():.2%}")
