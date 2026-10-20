# At the same score, did women's and men's loans go bad at the rate
# Mark II-R promised? Booked personal loans with a known outcome.
import json

import pandas as pd

from ballast import fairness
from ballast.config import ROOT
from ballast.scorecard import points, reject, sample

s = sample.load_sample()
s = s[s["outcome"].isin(["good", "bad"])]
s = s.merge(fairness.monitoring(), on="app_id", validate="1:1")
card = reject.load_refit("mark2_retro_ws").scorecard()
s["score"] = card.score(s)
s["promised"] = points.bad_rate_at(s["score"])
s["bad"] = s["outcome"].eq("bad").astype(int)
EDGES = [540, 560, 580, 600, 620]
band = pd.Series(pd.cut(s["score"], [0] + EDGES + [999], right=False,
                        labels=["<540", "540-559", "560-579", "580-599",
                                "600-619", "620+"]))
fm = s[s["gender"].isin(["F", "M"])]
t = fairness.calibration(fm["promised"], fm["bad"], fm["gender"],
                         band[fm.index])
print(f"{len(fm):,} loans to women and men, applied 2016 to mid-2024")
print(f"{'Mark II-R':<10}{'loans F':>9}{'seen F':>8}{'loans M':>9}"
      f"{'seen M':>8}{'promised':>10}")
fig = []
for b in band.cat.categories:
    f, m = t.loc[(b, "F")], t.loc[(b, "M")]
    promised = (f["promised"] + m["promised"]) / 2
    print(f"{b:<10}{int(f['n']):>9,}{f['seen']:>8.2%}{int(m['n']):>9,}"
          f"{m['seen']:>8.2%}{promised:>10.2%}")
    fig.append({"band": b, "F": round(f["seen"], 5),
                "M": round(m["seen"], 5),
                "promised": round(promised, 5)})
for g in ("F", "M"):
    x = fm[fm["gender"] == g]
    print(f"{g}: {len(x):,} loans, {x['bad'].sum()} bad, seen "
          f"{x['bad'].mean():.2%}, promised "
          f"{x['promised'].mean():.2%}, "
          f"score {x['score'].mean():.1f}")
e = fairness.group_effect(fm["promised"], fm["bad"],
                          fm["gender"].eq("F"))
print(f"Being a woman, once the score is known: {e['coef']:+.3f} on the"
      f" log odds\n  (standard error {e['se']:.3f}, p {e['p']:.3f})")
(ROOT / "code" / "13" / "04_calibration_by_gender.json").write_text(
    json.dumps(fig, indent=1) + "\n")
