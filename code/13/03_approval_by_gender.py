# Approval rates for women and men: Fernhill's decisions under Mark I,
# period by period, and Ballast's engine on the applicants of 2023-25.
import json

import numpy as np

from ballast import data, fairness
from ballast.config import ROOT, SEED
from ballast.decision import engine
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")]
apps = apps.merge(fairness.monitoring(), on="app_id", how="left",
                  validate="1:1").set_index(apps.index)
day = apps["app_date"].astype(str)
PERIODS = [("2016-01", "560"), ("2019-01", "575"), ("2020-04", "610"),
           ("2021-02", "525"), ("2022-07", "580")]
starts = [p[0] for p in PERIODS] + ["2026-01"]

print("Fernhill's decisions (Mark I), personal loans")
print(f"{'from':<9}{'cut-off':>8}{'women':>9}{'men':>8}{'ratio':>8}")
fig = {"periods": [], "ballast": {}}
for (start, cut), end in zip(PERIODS, starts[1:]):
    m = (day >= start) & (day < end)
    ok = apps.loc[m, "decision"].astype(str).eq("approve")
    t = fairness.rates(ok, apps.loc[m, "gender"])
    air = fairness.adverse_impact_ratio(ok, apps.loc[m, "gender"],
                                        "F", "M")
    print(f"{start:<9}{cut:>8}{t.loc['F', 'rate']:>9.1%}"
          f"{t.loc['M', 'rate']:>8.1%}{air:>8.3f}")
    fig["periods"].append({"from": start, "cutoff": cut,
                           "F": round(t.loc["F", "rate"], 5),
                           "M": round(t.loc["M", "rate"], 5)})

new = apps[day >= "2023-01-01"]
p = pol.load_policy()
d = engine.decide_all(new, p, engine.load_champion(p))
g = new["gender"]
rng = np.random.default_rng(SEED)
print(f"\nThe same {len(new):,} applicants of 2023-2025, two ways")
print(f"{'':<26}{'women':>8}{'men':>8}{'ratio':>8}  95% interval")
rows = [("Fernhill approved", new["decision"].astype(str) == "approve"),
        ("Ballast approves", d["decision"] == "approve"),
        ("Ballast refers", d["decision"] == "refer"),
        ("Ballast policy declines", d["stage"] == "policy")]
for name, flag in rows:
    t = fairness.rates(flag, g)
    air = fairness.adverse_impact_ratio(flag, g, "F", "M")
    lo, hi = fairness.air_interval(flag, g, "F", "M", rng)
    print(f"{name:<26}{t.loc['F', 'rate']:>8.1%}"
          f"{t.loc['M', 'rate']:>8.1%}{air:>8.3f}  "
          f"{lo:.3f} to {hi:.3f}")
    fig["ballast"][name] = {k: round(t.loc[k, "rate"], 5)
                            for k in ("F", "M")}
print("\nYear by year: Ballast's ratio (95% interval), Fernhill's,")
print("and the share of women and men Ballast declines by a rule")
yr = new["app_date"].astype(str).str[:4].to_numpy()
ok = (d["decision"] == "approve").to_numpy()
fern = (new["decision"].astype(str) == "approve").to_numpy()
rule = (d["stage"] == "policy").to_numpy()
gg = g.to_numpy()
for y in ("2023", "2024", "2025"):
    m = yr == y
    air = fairness.adverse_impact_ratio(ok[m], gg[m], "F", "M")
    lo, hi = fairness.air_interval(ok[m], gg[m], "F", "M", rng)
    fr = fairness.adverse_impact_ratio(fern[m], gg[m], "F", "M")
    r = fairness.rates(rule[m], gg[m])["rate"]
    print(f"  {y}  {air:.3f} ({lo:.3f} to {hi:.3f})  {fr:.3f}  "
          f"rules {r['F']:.1%} {r['M']:.1%}")
print("Also in 2023-2025: " + ", ".join(
    f"{k} {v:,}" for k, v in g.value_counts().loc[["X", "U"]].items()))
(ROOT / "code" / "13" / "03_approval_by_gender.json").write_text(
    json.dumps(fig, indent=1) + "\n")
