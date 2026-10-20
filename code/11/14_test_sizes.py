# How large and how long a champion-challenger test of the challenger
# against Mark II-R must be, at Fernhill's volumes.
import numpy as np
import pandas as pd

from ballast import data
from ballast.decision import policy as pol
from ballast.decision import strategy
from ballast.models import gbm
from ballast.scorecard import reject

raw = data.load_applications(unknowns=False)
p25 = raw[raw["product"].astype(str).eq("personal")
          & (raw["app_date"].astype(str) >= "2025-01-01")]
scored = pol.policy_reason(p25).isna()
per_month = scored.sum() / 12
ok = p25["decision"].astype(str).eq("approve")
took = p25.loc[ok, "outcome"].astype(str).eq("booked").mean()
print(f"2025: {len(p25) / 12:,.0f} personal applications a month, "
      f"{per_month:,.0f} past the rules;\n  {took:.0%} of approvals "
      "booked")

a = reject.frames(reject.applicants())["oot"]
a = a.merge(reject.retro(), on="app_id", how="left")
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
a = a[year == 2023].reset_index(drop=True)
champ = reject.load_refit("mark2_retro_ws").scorecard().score(a)
share = (champ >= 554).mean()
chall = strategy.top_share(gbm.load().score(a), share)
champ = (champ >= 554).to_numpy()
elsewhere = a["opened_elsewhere"].fillna(False).astype(bool)
seen = np.where(a["known"], a["bad"],
                np.where(elsewhere, a["bad_elsewhere"], np.nan))
t = strategy.swap_set(chall, champ, seen)
swap = t.loc["only A approves", "n"] / len(a)
p_in = t.loc["only A approves", "bad_rate"]
p_out = t.loc["only B approves", "bad_rate"]
both = t.loc["both approve", "bad_rate"]
print(f"\n2023 applicants, both approving {share:.1%}: they disagree"
      f"\n  on {2 * swap:.1%}")
print(f"  seen bad rate: challenger only {p_in:.1%}, "
      f"Mark II-R only {p_out:.1%},\n  both {both:.1%}")

p1 = (1 - swap / share) * both + swap / share * p_out   # champion arm
p2 = (1 - swap / share) * both + swap / share * p_in    # challenger arm
print("\nDesign 1: split every applicant at random, compare the arms")
n = strategy.n_per_arm(p1, p2)
per_arm = per_month * share * took / 2
print(f"  bad rate {p1:.2%} against {p2:.2%}: {n:,} loans an arm,")
print(f"  {per_arm:,.0f} a month each: "
      f"{strategy.months_to_run(n, per_month * share * took, 0.5)} "
      "months to the last outcome")
print("Design 2: decide the agreements as both say; split only"
      " the\n  disagreements, and compare those approved in each arm")
n2 = strategy.n_per_arm(p_out, p_in)
per_arm2 = per_month * swap * took / 2
print(f"  bad rate {p_out:.1%} against {p_in:.1%}: {n2:,} loans an "
      f"arm,\n  {per_arm2:,.1f} a month each: "
      f"{strategy.months_to_run(n2, per_month * swap * took, 0.5)}"
      " months to the last outcome")
year_n = int(per_arm2 * 12)
print(f"  after a year ({year_n} an arm) it could tell {p_out:.1%}"
      f"\n  only from {strategy.detectable(p_out, year_n):.1%} or less")
