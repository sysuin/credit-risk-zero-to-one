# The people around the score: what Mark II-R says about the loans
# branch managers made against Mark I, and the fair-lending measures
# Chapter 13 left open, re-performed.
import numpy as np
import pandas as pd

from ballast import fairness
from ballast.config import BALLAST, SEED
from ballast.scorecard import points, reject, sample

card = reject.load_refit("mark2_retro_ws").scorecard()
a = reject.applicants()
o = a[(a["override"] == "low_side") & (a["outcome"] == "booked")].copy()
o["score"] = card.score(o)
o["promised"] = points.bad_rate_at(o["score"])
known = o[o["bad"].notna()]
print(f"Low-side overrides booked 2016 to mid-2024: {len(o)}, "
      f"{len(known)} with\nan outcome, {int(known['bad'].sum())} bad "
      f"({known['bad'].mean():.1%}); Mark II-R promised "
      f"{known['promised'].mean():.1%}")
for name, m in (("approved by Mark II-R", known["score"] >= 554),
                ("declined by Mark II-R", known["score"] < 550)):
    g = known[m]
    print(f"  {name}: {len(g):>3} loans, bad {g['bad'].mean():>6.1%},"
          f" promised {g['promised'].mean():.1%}")

dec = pd.read_parquet(BALLAST / "decision" / "decisions_2025.parquet")
dec = dec.merge(fairness.monitoring(), on="app_id", validate="1:1")
ok = dec["decision"].eq("approve").to_numpy()
air = fairness.adverse_impact_ratio(ok, dec["gender"], "F", "M")
lo, hi = fairness.air_interval(ok, dec["gender"], "F", "M",
                               np.random.default_rng(SEED))
print(f"\n2025 applications decided by Ballast: {len(dec):,}; approval"
      f" F/M {air:.3f}\n  (95% interval {lo:.3f} to {hi:.3f})")
s = sample.load_sample()
s = s[s["outcome"].isin(["good", "bad"])].copy()
s["promised"] = points.bad_rate_at(card.score(s))
e = fairness.group_effect(s["promised"], s["bad"],
                          (s["age"] - 40) / 10)
print(f"Age, booked loans 2016 to mid-2024 ({len(s):,}): each decade "
      f"adds\n  {e['coef']:+.3f} to the log odds of bad at the same "
      f"score (p {e['p']:.5f})")
