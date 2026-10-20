# Reasons measured against the cut-off instead of each line's best bin,
# for every 2025 application Ballast declined or referred at the score.
import json

from ballast import data, fairness
from ballast.config import ROOT
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import reject

p = pol.load_policy()
card = engine.load_champion(p)
ref_apps = reject.frames(reject.applicants())["oot"]
ref = fairness.cutoff_reference(card, ref_apps, p.cutoff)
at = card.score(ref_apps).between(p.cutoff, p.cutoff + 3).sum()
best = card.table.groupby("characteristic", sort=False)["points"].max()
print(f"Reference: {at} applicants of 2023 to mid-2024 scoring "
      f"{p.cutoff}-{p.cutoff + 3}")
print(f"  {'line':<24}{'best bin':>9}{'at cut-off':>12}")
for name in card.characteristics:
    print(f"  {name:<24}{best[name]:>9}{ref[name]:>12.1f}")

raw = data.load_applications(unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
d = engine.decide_all(apps, p, card)
m = (d["stage"] == "score") & (d["decision"] != "approve")
old = d.loc[m, "reasons"]
new = fairness.cutoff_reasons(card, engine.prepare(apps[m]), ref)
print(f"\nFirst reason, {m.sum():,} score declines and referrals, 2025")
print(f"  {'':<24}{'best bin':>10}{'cut-off':>9}")
counts = {"best bin": old.str[0].value_counts(),
          "cut-off": new.str[0].value_counts()}
names = counts["cut-off"].index.union(counts["best bin"].index)
order = sorted(names, key=lambda n: -counts["cut-off"].get(n, 0))
for n in order:
    print(f"  {n:<24}{counts['best bin'].get(n, 0):>10,}"
          f"{counts['cut-off'].get(n, 0):>9,}")
for label, r in (("best bin", old), ("cut-off", new)):
    act = r.str[0].map(engine.actionable).mean()
    print(f"{label}: {r.map(len).mean():.1f} reasons each; first "
          f"reason one they can act on {act:.0%}")
same = (old.str[0] == new.str[0]).mean()
print(f"Same first reason both ways: {same:.1%}")
(ROOT / "code" / "13" / "09_reasons_against_cutoff.json").write_text(
    json.dumps({k: {n: int(v.get(n, 0)) for n in order}
                for k, v in counts.items()}, indent=1) + "\n")
