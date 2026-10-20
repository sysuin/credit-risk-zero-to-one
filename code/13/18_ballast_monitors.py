# Ballast's fair-lending and fraud report on its own 2025 decisions:
# the engine decides, fairness.py measures, fraud.py refers.
import numpy as np

from ballast import data, fairness, fraud
from ballast.config import SEED
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import reject

p = pol.load_policy()
card = engine.load_champion(p)
raw = data.load_applications(unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
d = engine.decide_all(apps, p, card)
g = apps[["app_id"]].merge(fairness.monitoring(), on="app_id",
                           how="left")["gender"].to_numpy()
ok = (d["decision"] == "approve").to_numpy()
air = fairness.adverse_impact_ratio(ok, g, "F", "M")
lo, hi = fairness.air_interval(ok, g, "F", "M",
                               np.random.default_rng(SEED))
t = fairness.rates(ok, g)
print(f"{len(d):,} decisions, 2025. Approved: women "
      f"{t.loc['F', 'rate']:.1%}, men {t.loc['M', 'rate']:.1%}")
print(f"  adverse impact ratio {air:.3f} ({lo:.3f} to {hi:.3f})")
band = fairness.age_band(apps["age"]).astype(str).to_numpy()
r = fairness.rates(ok, band)["rate"]
print("  by age: " + ", ".join(
    f"{b} {r[b]:.0%}" for b in fairness.AGE_LABELS))

ref = fairness.cutoff_reference(
    card, reject.frames(reject.applicants())["oot"], p.cutoff)
m = (d["stage"] == "score") & (d["decision"] != "approve")
why = fairness.cutoff_reasons(card, engine.prepare(apps[m]), ref)
top = why.str[0].value_counts()
print(f"{m.sum():,} score declines and referrals; first reasons:")
for code, n in top.head(3).items():
    print(f"  {engine.reason_text((code,))[0]:<40}{n:>6,}")

sent = fraud.referred(fraud.flags(apps))
print(f"Fraud referrals at {fraud.REFER_AT}+ flags: {sent.sum()}, of "
      f"which the engine\n  would approve "
      f"{int((sent & (d['decision'] == 'approve')).sum())} and refer "
      f"{int((sent & (d['decision'] == 'refer')).sum())}")
