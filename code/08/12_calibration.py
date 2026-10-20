# Does a score's bad rate come true? Predicted vs observed by band.
import json

from ballast.config import ROOT
from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)
det = s[s["outcome"] != "indeterminate"].copy()
det["score"] = card.score(det)
det["p_bad"] = points.bad_rate_at(det["score"])
edges = [540, 560, 580, 600, 620, 640]

out = {}
for split in ("out_of_time", "holdout"):
    d = det[det["split"] == split]
    t = metrics.calibration(d["score"], d["bad"], d["p_bad"], edges)
    hl, df, p = metrics.hosmer_lemeshow(d["p_bad"], d["bad"])
    out[split] = t.round(6).to_dict(orient="records")
    if split == "out_of_time":
        print(f"{'band':<9}{'loans':>7}{'bads':>6}{'expected':>10}"
              f"{'observed':>10}{'predicted':>11}{'p':>7}")
        for _, r in t.iterrows():
            print(f"{r['band']:<9}{r['loans']:>7,}{r['bads']:>6}"
                  f"{r['expected']:>10.1f}{r['observed']:>10.2%}"
                  f"{r['predicted']:>11.2%}{r['p_value']:>7.2f}")
    print(f"{split}: observed {d['bad'].mean():.2%}, predicted "
          f"{d['p_bad'].mean():.2%}")
    print(f"  Hosmer-Lemeshow {hl:.1f} on {df} df, p {p:.3f}")

# The same ranking with every score 20 points higher.
d = det[det["split"] == "out_of_time"]
up = d["score"] + 20
hl, df, p = metrics.hosmer_lemeshow(points.bad_rate_at(up), d["bad"])
print(f"every score +20: Gini {metrics.gini(d['score'], d['bad']):.3f}"
      f" -> {metrics.gini(up, d['bad']):.3f}, predicted "
      f"{points.bad_rate_at(up).mean():.2%}")
print(f"  Hosmer-Lemeshow {hl:.1f} on {df} df, p {p:.1e}")

path = ROOT / "code" / "08" / "12_calibration.json"
path.write_text(json.dumps(out, indent=1) + "\n")
