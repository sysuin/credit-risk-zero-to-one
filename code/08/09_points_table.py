# Mark II as a points table: the thing a credit officer reads.
import json

from ballast.config import ROOT
from ballast.scorecard import model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)

print(f"{'base':<22}{card.base:>4}")
for name in card.characteristics:
    rows = card.table[card.table["characteristic"] == name]
    cells = [f"{b} {p}" for b, p in zip(rows["bin"], rows["points"])]
    print(f"{name:<22}" + "  ".join(cells[:3]))
    if len(cells) > 3:
        print(f"{'':<22}" + "  ".join(cells[3:]))
top = card.table.groupby("characteristic")["points"].max().sum()
print(f"lowest possible score {card.base}, highest {card.base + top}")

scored = card.score(s)
exact = points.exact_score(mark2.params.to_dict(), bins, s)
print(f"rounding: largest gap from the exact score "
      f"{(scored - exact).abs().max():.2f} points")

# Save the table for the figure: one entry per line of the card.
lines = []
for n in card.characteristics:
    rows = card.table[card.table["characteristic"] == n]
    lines.append({"name": n,
                  "bins": rows["bin"].tolist(),
                  "points": rows["points"].tolist(),
                  "coef": round(float(mark2.params[n]), 3)})
out = {"base": card.base, "lines": lines}
path = ROOT / "code" / "08" / "09_points_table.json"
path.write_text(json.dumps(out, indent=1) + "\n")
