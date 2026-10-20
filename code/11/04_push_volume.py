# What the growth push did to volume: personal-loan applications,
# approvals and loans per month, under each policy.
import pandas as pd

from ballast import data

raw = data.load_applications(unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")].copy()
p["day"] = pd.to_datetime(p["app_date"].astype("datetime64[s]"))
PERIODS = [("Jan 2019-Mar 2020", 575, "2019-01", "2020-03"),
           ("Apr 2020-Jan 2021", 610, "2020-04", "2021-01"),
           ("Feb 2021-Jun 2022", 525, "2021-02", "2022-06"),
           ("Jul 2022-Dec 2023", 580, "2022-07", "2023-12"),
           ("Jan 2024-Dec 2025", 580, "2024-01", "2025-12")]
print(f"{'applied':<18}{'cut':>4}{'apps':>6}{'appr':>6}{'loans':>6}"
      f"{'rate':>7}{'took':>6}{'broker':>8}")
for name, cut, lo, hi in PERIODS:
    month = p["day"].dt.to_period("M")
    g = p[month.between(pd.Period(lo), pd.Period(hi))]
    months = (pd.Period(hi) - pd.Period(lo)).n + 1
    ok = g["decision"].astype(str).eq("approve")
    booked = g["outcome"].astype(str).eq("booked")
    broker = g["channel"].astype(str).eq("broker")
    print(f"{name:<18}{cut:>4}{len(g) / months:>6.0f}"
          f"{ok.sum() / months:>6.0f}{booked.sum() / months:>6.0f}"
          f"{ok.mean():>7.1%}{booked.sum() / ok.sum():>6.0%}"
          f"{broker.mean():>8.1%}")
print("apps, appr, loans: a month; took: loans per approval")
push = p["day"].between("2021-02-01", "2022-06-30")
ok = p["decision"].astype(str).eq("approve")
for chan in ("broker", "branch", "online"):
    m = push & ok & p["channel"].astype(str).eq(chan)
    took = p.loc[m, "outcome"].astype(str).eq("booked").mean()
    print(f"push approvals through {chan:<7}{int(m.sum()):>6,},"
          f" taken up {took:.0%}")
