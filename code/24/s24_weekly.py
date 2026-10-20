# Exercise 24.1: the bureau line week by week around July 2019, each
# week against the 52 weeks before 1 July, with its noise level.
import pandas as pd

from ballast import data
from ballast import monitoring as mon
from ballast.decision import policy

raw = data.load_applications(unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")]
day = pd.to_datetime(pl["app_date"].astype("datetime64[s]"))
line = policy.mark1_lines(pl)["bureau_score"]
ref = line[(day >= "2018-07-02") & (day < "2019-07-01")]
week = day.dt.to_period("W-SUN")
print(f"{'week starting':<15}{'apps':>6}{'PSI':>8}{'noise':>8}  alarm")
for w in sorted(week[(day >= "2019-06-03") & (day < "2019-08-05")]
                .unique()):
    now = line[week == w]
    bands = len(set(ref) | set(now))
    p = mon.category_psi(ref, now)
    n = mon.psi_noise(len(now), len(ref), bands)
    print(f"{str(w.start_time.date()):<15}{len(now):>6}{p:>8.3f}"
          f"{n:>8.3f}  {'yes' if p >= n else ''}")
