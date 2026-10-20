# Exercise 29.4: what a limit of 40 points below the cut-off, instead
# of 80, would have stopped, and how those loans went.
import fernhill
from ballast import governance as gv

con = fernhill.connect()
a = gv.scored_applications(con)
low = a[a.override == "low_side"]
b = a[a.outcome == "booked"].merge(gv.first_year_bad(con),
                                   on="account_id")
ov = b[b.override == "low_side"]
print(f"{'limit':<7}{'stopped':>8}{'loans':>7}{'bad':>8}"
      f"{'kept loans':>12}{'bad':>8}")
for limit in (80, 40):
    stop, keep = ov[ov.margin < -limit], ov[ov.margin >= -limit]
    print(f"{limit:<7}{(low.margin < -limit).sum():>8}{len(stop):>7}"
          f"{stop.bad.mean():>8.1%}{len(keep):>12}"
          f"{keep.bad.mean():>8.1%}")
