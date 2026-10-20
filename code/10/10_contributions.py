# One applicant's challenger score, split into its characteristics.
from ballast.models import gbm, reasons
from ballast.scorecard import points, sample

s = sample.load_sample()
model = gbm.fit(s)
card = points.load_scorecard()
oot = s[s["split"] == "out_of_time"].sort_values("app_id")
row = oot.iloc[[0]]
pts = reasons.in_points(model, row).iloc[0]
mk2 = card.line_points(row).iloc[0]

print(f"{row['app_id'].iloc[0]}: challenger "
      f"{model.score(row).iloc[0]:.1f}, Mark II "
      f"{card.score(row).iloc[0]}")
print(f"{'characteristic':<24}{'value':>9}{'challenger':>12}"
      f"{'Mark II':>9}")
print(f"{'average applicant':<33}{pts['base']:>12.1f}"
      f"{'base ' + str(card.base):>9}")
order = pts.drop("base").abs().sort_values(ascending=False).index
for name in order[:8]:
    v = row[name].iloc[0]
    shown = v if isinstance(v, str) else f"{v:,.2f}".rstrip(
        "0").rstrip(".")
    m = f"{mk2[name]:.0f}" if name in mk2 else ""
    print(f"{name:<24}{shown:>9}{pts[name]:>+12.1f}{m:>9}")
rest = pts[order[8:]]
print(f"{f'the other {len(rest)}':<33}{rest.sum():>+12.1f}")
total = pts.sum()
print(f"{'total':<33}{total:>12.1f}")
gap = abs(total - model.score(row).iloc[0])
print(f"adds up to the challenger's score (within 1e-9): {gap < 1e-9}")
