# Exercise 13.2: reasons measured against the average applicant who
# reached the score, instead of the applicants at the cut-off.
from ballast import data, fairness
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import reject

p = pol.load_policy()
card = engine.load_champion(p)
oot = reject.frames(reject.applicants())["oot"]
at_cut = fairness.cutoff_reference(card, oot, p.cutoff)
everyone = card.line_points(oot).mean().rename("reference")
raw = data.load_applications(unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
d = engine.decide_all(apps, p, card)
m = (d["stage"] == "score") & (d["decision"] != "approve")
chars = engine.prepare(apps[m])
a = fairness.cutoff_reasons(card, chars, at_cut).str[0]
b = fairness.cutoff_reasons(card, chars, everyone).str[0]
print(f"{'first reason':<24}{'at cut-off':>11}{'all applicants':>16}")
for n in a.value_counts().index.union(b.value_counts().index):
    print(f"{n:<24}{(a == n).sum():>11,}{(b == n).sum():>16,}")
print(f"same first reason {(a == b).mean():.1%}")
print("bureau score points: at cut-off "
      f"{at_cut['bureau_score']:.1f}, all applicants "
      f"{everyone['bureau_score']:.1f}")
