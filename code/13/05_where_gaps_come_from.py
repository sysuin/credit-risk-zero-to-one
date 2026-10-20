# Where women's and men's applications differ: income, the score lines
# that read it, and the amounts and limits that are set from it.
import pandas as pd

from ballast import data, fairness
from ballast.decision import engine
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
raw = raw.merge(fairness.monitoring(), on="app_id", validate="1:1")
raw = raw[raw["gender"].isin(["F", "M"])]
recent = raw[raw["app_date"].astype(str) >= "2023-01-01"]
inc = recent["stated_income_cents"].astype(float) / 100
print("Applicants 2023-2025, all products: median stated income")
med = inc.groupby(recent["gender"]).median()
print(f"  women ${med['F']:,.0f}, men ${med['M']:,.0f}, "
      f"ratio {med['F'] / med['M']:.3f}")

pl = recent[recent["product"].astype(str).eq("personal")]
p = pol.load_policy()
card = engine.load_champion(p)
d = engine.decide_all(pl, p, card)
scored = (d["stage"] == "score").to_numpy()
lines = card.line_points(engine.prepare(pl))[scored]
g = pl["gender"].to_numpy()[scored]
mean = lines.groupby(g).mean()
gap = (mean.loc["F"] - mean.loc["M"]).sort_values()
print("\nMark II-R points, women minus men (personal, past the rules)")
for name, v in gap.items():
    if abs(v) >= 0.05:
        print(f"  {name:<24}{v:+.2f}")
print(f"  {'score':<24}{gap.sum():+.2f}")

ok = d["decision"].eq("approve").to_numpy()
band = pd.qcut(pl["stated_income_cents"].astype(float), 4,
               labels=["lowest", "second", "third", "highest"])
t = pd.DataFrame({"band": band.array, "g": pl["gender"].to_numpy(),
                  "ok": ok}).groupby(["band", "g"], observed=True)["ok"]
r = t.mean().unstack()
print("\nBallast approves, by quarter of stated income")
for b, row in r.iterrows():
    print(f"  {b:<9} women {row['F']:6.1%}   men {row['M']:6.1%}")

cards = recent[recent["product"].astype(str).eq("card")
               & recent["decision"].astype(str).eq("approve")]
lim = cards["offered_amount_cents"].astype(float) / 100
share = lim / (cards["stated_income_cents"].astype(float) / 100)
print("\nCard limits Fernhill offered, 2023-2025: median")
for gg in ("F", "M"):
    m = cards["gender"] == gg
    print(f"  {gg}: limit ${lim[m].median():,.0f}, "
          f"{share[m].median():.1%} of stated income, "
          f"{m.sum():,} cards")
