# Mark II-R at 554 against what Fernhill decided for the same
# applicants: who changes side, and what the lender can see of them.
import numpy as np

from ballast.decision import strategy
from ballast.scorecard import points, reject

a = reject.frames(reject.applicants())["oot"]
a = a.merge(reject.retro(), on="app_id", how="left")
score = reject.load_refit("mark2_retro_ws").scorecard().score(a)
elsewhere = a["opened_elsewhere"].fillna(False).astype(bool)
seen = np.where(a["known"], a["bad"],
                np.where(elsewhere, a["bad_elsewhere"], np.nan))
ballast = (score >= 554).to_numpy()
fern = a["outcome"].ne("declined").to_numpy()
t = strategy.swap_set(ballast, fern, seen, points.bad_rate_at(score))
t.index = ["both approve", "only Mark II-R", "only Fernhill",
           "both decline"]
print("Applicants Jan 2023-Jun 2024: Mark II-R at 554 (A)"
      " and Fernhill (B)")
print(f"  {'':<16}{'people':>7}{'seen':>7}{'bad rate':>10}"
      f"{'promised':>10}")
for name, r in t.iterrows():
    print(f"  {name:<16}{int(r['n']):>7,}{int(r['known']):>7,}"
          f"{r['bad_rate']:>10.1%}{r['promised']:>10.1%}")
print("\nAmong approvals whose outcome was seen")
for name, ap in (("Mark II-R at 554", ballast), ("Fernhill", fern)):
    m = ap & ~np.isnan(seen)
    print(f"  {name:<18}{int(m.sum()):>6,} seen, bad rate "
          f"{np.nanmean(seen[m]):.2%}")
booked = a["known"].to_numpy() & ~np.isnan(seen)
print(f"\nBooked loans: Mark II-R promised "
      f"{points.bad_rate_at(score)[booked].mean():.2%}, "
      f"{seen[booked].mean():.2%} went bad")
