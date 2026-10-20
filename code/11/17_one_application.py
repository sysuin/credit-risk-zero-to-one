# One 2025 application that Fernhill approved and Ballast declines,
# followed through both decisions line by line.
from ballast import data
from ballast.decision import engine
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
p = pol.load_policy()
card = engine.load_champion(p)
d = engine.decide_all(apps, p, card)
pick = d[(d["decision"] == "decline") & (d["stage"] == "score")
         & apps["decision"].astype(str).eq("approve")].index[0]
app = apps.loc[[pick]]
r = app.iloc[0]
print(f"{r['app_id']}, {r['app_date']}, {r['channel']}, "
      f"${r['amount_requested_cents'] / 100:,.0f} over "
      f"{r['term_requested_months']} months")
print(f"Fernhill: Mark I {r['mark1_score']} against {r['cutoff']}"
      f" -> {r['decision']}, {r['outcome']}")

lines = card.explain(engine.prepare(app).iloc[0])
best = card.table.groupby("characteristic", sort=False)["points"].max()
print(f"\nMark II-R, line by line (base {card.base})")
print(f"  {'line':<22}{'bin':<16}{'points':>7}{'best':>6}")
for _, ln in lines.iterrows():
    print(f"  {ln['characteristic']:<22}{str(ln['bin']):<16}"
          f"{ln['points']:>7}{best[ln['characteristic']]:>6}")
dec = engine.decide(app, p, card)
print(f"  {'score':<38}{dec.score:>7}")
print(f"\nBallast: {dec.decision} at the {dec.stage} "
      f"(cut-off {p.cutoff}, refer from {p.cutoff - p.refer_below})")
for k, (code, text) in enumerate(zip(dec.reasons,
                                     engine.reason_text(dec.reasons))):
    act = "can act" if engine.actionable(code) else "cannot act"
    print(f"  {k + 1}. {text} ({act})")
