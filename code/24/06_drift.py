# Is Mark II-R still ranking, and still keeping its promises? The
# Gini by year and the calibration by quarter, with intervals.
import pandas as pd

from ballast import monitoring as mon
from ballast.scorecard import points, reject, sample

s = sample.load_sample()
s = s[s["outcome"].isin(["good", "bad"])].copy()
card = reject.load_refit("mark2_retro_ws").scorecard()
s["score"] = card.score(s)
s["promised"] = points.bad_rate_at(s["score"])
s["bad"] = s["outcome"].eq("bad").astype(int)
day = pd.to_datetime(s["app_date"].astype("datetime64[s]"))
g = mon.gini_drift(s["score"], s["bad"], day.dt.year)
print("Mark II-R on booked personal loans, by year applied")
print(f"{'year':<6}{'loans':>7}{'bads':>6}{'Gini':>7}"
      f"{'95% interval':>17}")
for r in g.itertuples():
    print(f"{r.period:<6}{r.n:>7,}{r.bads:>6}{r.gini:>7.3f}"
          f"{r.lo:>10.3f} to {r.hi:.3f}")
c = mon.calibration_drift(s["promised"], s["bad"],
                          day.dt.to_period("Q").astype(str))
print("\nBy quarter applied: promised and seen bad rates")
print(f"{'quarter':<9}{'loans':>6}{'bads':>5}{'promised':>9}{'seen':>7}"
      f"{'seen/prom':>10}{'95% interval':>15}")
for r in c[c["period"] >= "2022Q1"].itertuples():
    flag = "  *" if r.outside else ""
    print(f"{r.period:<9}{r.n:>6}{r.bads:>5}{r.promised:>9.2%}"
          f"{r.seen:>7.2%}{r.ratio:>10.2f}{r.lo:>8.2%}-{r.hi:.2%}"
          f"{flag}")
hi = c[c.outside & (c.ratio > 1)]
print(f"* promise outside the interval: {c.outside.sum()} of "
      f"{len(c)} quarters since 2016Q1,")
print(f"  {len(hi)} of them above the promise ("
      + ", ".join(hi.period) + ")")
print(f"  seen/promised from {c.ratio.min():.2f} to "
      f"{c.ratio.max():.2f}")
