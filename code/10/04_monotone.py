# What the constraints cost, and what the unconstrained model does.
# timeout: 300
import json

import numpy as np

from ballast.config import ROOT
from ballast.models import gbm
from ballast.scorecard import metrics, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"]
oot = det[det["split"] == "out_of_time"]
models = {"constrained": gbm.fit(s), "free": gbm.fit(s, monotone={})}

print(f"{'':<14}{'trees':>6}{'holdout':>9}{'out of time':>13}")
for name, m in models.items():
    sc = m.score(det)
    g = [metrics.gini(sc[det["split"] == k], det.loc[
        det["split"] == k, "bad"]) for k in ("holdout", "out_of_time")]
    print(f"{name:<14}{m.rounds:>6}{g[0]:>9.3f}{g[1]:>13.3f}")

# Move one characteristic the risky way for every out-of-time
# applicant: for what share does the predicted risk fall?
moves = [("dti", 0.05, "+0.05"), ("revolving_utilisation", 0.10,
         "+0.10"), ("enquiries_6m", 1, "+1"), ("bureau_score", -20,
         "-20"), ("worst_status_24m", 30, "+30 days")]
print()
print(f"{'made riskier':<30}{'risk falls, free':>18}"
      f"{'constrained':>13}")
for name, step, shown in moves:
    shares = [gbm.wrong_way(m, oot, name, abs(step),
                            riskier=1 if step > 0 else -1)
              for m in (models["free"], models["constrained"])]
    print(f"{name + ' ' + shown:<30}{shares[0]:>18.1%}"
          f"{shares[1]:>13.1%}")

grid = np.round(np.arange(0, 1.15, 0.05), 2)
name = "revolving_utilisation"
out = {"grid": grid.tolist(), "average": {}, "one": {}}
for k, m in models.items():
    out["average"][k] = gbm.partial_dependence(
        m, oot, name, grid).round(5).tolist()
# The applicant the free model moves the wrong way the most: the
# largest total fall in risk as utilisation rises.
f = oot[oot[name].notna()]
curves = np.column_stack([models["free"].raw(f.assign(**{name: v}))
                          for v in grid])
fall = np.clip(-np.diff(curves, axis=1), 0, None).sum(axis=1)
who = f.iloc[[int(np.argmax(fall))]]
for k, m in models.items():
    out["one"][k] = [round(float(m.raw(who.assign(**{name: v}))[0]),
                           5) for v in grid]
out["app_id"] = who["app_id"].iloc[0]
print()
print(f"largest wrong-way move, free model: {out['app_id']}, "
      f"utilisation {who[name].iloc[0]:.2f}")
path = ROOT / "code" / "10" / "04_monotone.json"
path.write_text(json.dumps(out) + "\n")
