# Mark II-R's strategy curve on the applicants of 2023 and early 2024,
# Fernhill's cut-offs placed on it, and the cut-off the limits choose.
import json

import fernhill
from ballast.config import ROOT
from ballast.decision import strategy
from ballast.scorecard import points, reject, sample

a = reject.frames(reject.applicants())["oot"]
card = reject.load_refit("mark2_retro_ws").scorecard()
score = card.score(a)
p_bad = points.bad_rate_at(score)
c = strategy.curve(score, p_bad, range(530, 601))
print(f"{len(a):,} applicants, Jan 2023-Jun 2024, who passed the rules")
print(f"{'cut-off':>8}{'approve':>9}{'bad rate':>10}{'marginal':>10}")
for _, r in c[c["cutoff"].isin(range(540, 581, 5))].iterrows():
    print(f"{r['cutoff']:>8.0f}{r['approval']:>9.1%}"
          f"{r['bad_rate']:>10.2%}{r['marginal']:>10.2%}")

fern = a["outcome"].ne("declined").to_numpy()
today = float(p_bad[fern].mean())
print(f"\nFernhill's decisions: approved {fern.mean():.1%}, "
      f"expected bad rate {today:.2%}")
print("Mark I's cut-offs on the same applicants:")
marks = []
for cut in (610, 580, 575, 560, 525):
    ap = (a["mark1_score"] >= cut).to_numpy()
    marks.append({"cutoff": cut, "approval": float(ap.mean()),
                  "bad_rate": float(p_bad[ap].mean())})
    print(f"  {cut}: approve {ap.mean():.1%}, "
          f"expected bad rate {p_bad[ap].mean():.2%}")

con = fernhill.connect()
eco = strategy.loan_economics(con, "personal")
s = sample.load_sample()
s = s[s["app_date"].astype(str).between("2019-01-01", "2021-12-31")]
d = s[["account_id", "outcome"]].merge(eco, on="account_id")
_, even = strategy.break_even(
    d.loc[d["outcome"] == "good", "profit"].mean(),
    -d.loc[d["outcome"] == "bad", "profit"].mean())
limit = 2 / 3 * even
cut = strategy.choose_cutoff(c, max_bad_rate=today, max_marginal=limit)
r = c.set_index("cutoff").loc[cut]
print(f"\nLimits: bad rate at most {today:.2%}; marginal at most "
      f"{limit:.2%}\n  (two thirds of the break-even {even:.1%})")
print(f"Chosen cut-off {cut}: approve {r['approval']:.1%}, expected "
      f"bad rate {r['bad_rate']:.2%},\n  marginal {r['marginal']:.2%}")
best = card.table.groupby("characteristic")["points"].max().sum()
m1 = a["mark1_score"]
print(f"Scores: Mark II-R {card.base} to {card.base + best}; "
      f"Mark I here {m1.min():.0f} to {m1.max():.0f}")
in_band = (a["mark1_score"] >= 570) & (a["mark1_score"] < 590)
w = strategy.refer_band(score, cut, in_band.mean())
held = ((score >= cut - w) & (score < cut + w)).mean()
print(f"Refer band: Mark I's held {in_band.mean():.1%} of applicants;"
      f"\n  {cut - w} to {cut + w - 1} holds {held:.1%}")
out = ROOT / "code" / "11" / "09_strategy_curve.json"
out.write_text(json.dumps({
    "curve": c[["cutoff", "approval", "bad_rate", "marginal"]]
    .round(5).to_dict("records"),
    "fernhill": {"approval": round(float(fern.mean()), 5),
                 "bad_rate": round(today, 5)},
    "mark1": [{k: (round(v, 5) if isinstance(v, float) else v)
               for k, v in m.items()} for m in marks],
    "chosen": cut, "refer": [cut - w, cut + w - 1],
    "break_even": round(float(even), 5)}, indent=1) + "\n")
