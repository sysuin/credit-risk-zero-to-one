# The complainant's application through Ballast: her score line by
# line, and the reasons each method would put in her letter.
import json

from ballast import data, fairness
from ballast.config import ROOT
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import reject

p = pol.load_policy()
card = engine.load_champion(p)
ref = fairness.cutoff_reference(
    card, reject.frames(reject.applicants())["oot"], p.cutoff)
raw = data.load_applications(unknowns=False)
app = raw[raw["app_id"] == "A00073784"]
chars = engine.prepare(app)
dec = engine.decide(app, p, card)
best = card.table.groupby("characteristic", sort=False)["points"].max()
pts = card.line_points(chars).iloc[0]
gap = fairness.gaps(card, chars, ref).iloc[0]
print(f"A00073784: Mark II-R {dec.score}, {dec.decision} "
      f"(cut-off {p.cutoff}, refer {p.cutoff - p.refer_below}-"
      f"{p.cutoff + p.refer_above - 1})")
print(f"  {'line':<24}{'points':>7}{'best':>6}{'short':>7}"
      f"{'at cut-off':>12}{'gap':>7}")
for n in card.characteristics:
    print(f"  {n:<24}{pts[n]:>7}{best[n]:>6}{best[n] - pts[n]:>7}"
          f"{ref[n]:>12.1f}{gap[n]:>+7.1f}")
print(f"  gaps add up to {gap.sum():+.1f}: the reference applicant's "
      f"{card.base + ref.sum():.1f}\n  less her {dec.score}")
new = fairness.cutoff_reasons(card, chars, ref).iloc[0]
out = {}
for label, rs in (("Best bin (Chapter 11)", dec.reasons),
                  ("Against the cut-off", new)):
    print(f"\n{label}:")
    out[label] = []
    for k, (code, text) in enumerate(zip(rs, engine.reason_text(rs))):
        act = "can act" if engine.actionable(code) else "cannot act"
        print(f"  {k + 1}. {text} ({act})")
        out[label].append({"code": code, "text": text,
                           "short": int(best[code] - pts[code]),
                           "gap": round(float(gap[code]), 1),
                           "actionable": engine.actionable(code)})
(ROOT / "code" / "13" / "10_her_letter.json").write_text(
    json.dumps({"score": dec.score, "reasons": out}, indent=1) + "\n")
