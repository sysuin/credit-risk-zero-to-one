# Does the challenger's predicted bad rate come true, band by band?
import json

from ballast.config import ROOT
from ballast.models import gbm
from ballast.scorecard import metrics, points, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"].copy()
challenger = gbm.fit(s)
det["score"] = challenger.score(det)
det["p_bad"] = challenger.p_bad(det)
det["mark2_p"] = points.bad_rate_at(points.load_scorecard().score(det))
edges = [540, 560, 580, 600, 620, 640]

d = det[det["split"] == "out_of_time"]
t = metrics.calibration(d["score"], d["bad"], d["p_bad"], edges)
print("challenger, out-of-time loans, by band on Mark II's scale")
print(f"{'band':<9}{'loans':>7}{'bads':>6}{'expected':>10}"
      f"{'observed':>10}{'predicted':>11}{'p':>7}")
for _, r in t.iterrows():
    print(f"{r['band']:<9}{r['loans']:>7,}{r['bads']:>6}"
          f"{r['expected']:>10.1f}{r['observed']:>10.2%}"
          f"{r['predicted']:>11.2%}{r['p_value']:>7.2f}")
print()
print(f"{'':<12}{'observed':>10}{'challenger':>12}{'HL p':>7}"
      f"{'Mark II':>9}{'HL p':>7}")
for split in ("train", "holdout", "out_of_time"):
    d = det[det["split"] == split]
    p1 = metrics.hosmer_lemeshow(d["p_bad"], d["bad"],
                                 fitted_here=split == "train")[2]
    p2 = metrics.hosmer_lemeshow(d["mark2_p"], d["bad"],
                                 fitted_here=split == "train")[2]
    print(f"{split:<12}{d['bad'].mean():>10.2%}"
          f"{d['p_bad'].mean():>12.2%}"
          f"{p1:>7.3f}{d['mark2_p'].mean():>9.2%}{p2:>7.3f}")
print()
print("applicants with no bureau file")
print(f"{'':<12}{'loans':>6}{'bads':>6}{'observed':>10}"
      f"{'challenger':>12}{'Mark II':>9}")
for split in ("train", "holdout", "out_of_time"):
    d = det[(det["split"] == split) & det["bureau_score"].isna()]
    print(f"{split:<12}{len(d):>6}{d['bad'].sum():>6}"
          f"{d['bad'].mean():>10.1%}{d['p_bad'].mean():>12.1%}"
          f"{d['mark2_p'].mean():>9.1%}")

path = ROOT / "code" / "10" / "07_calibration.json"
path.write_text(json.dumps(t.round(6).to_dict(orient="records"),
                           indent=1) + "\n")
