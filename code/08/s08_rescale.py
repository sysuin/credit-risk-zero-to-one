# Mark II on another scale: 500 points at 20 to 1, 40 to double.
import math

import numpy as np

from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
d = s[(s["split"] == "out_of_time") & (s["outcome"] != "indeterminate")]
old = points.exact_score(mark2.params.to_dict(), bins, d)
log_odds = (old - points.OFFSET) / points.FACTOR

factor = 40 / math.log(2)
offset = 500 - factor * math.log(20)
new = offset + factor * log_odds
print(f"new factor {factor:.4f}, offset {offset:.4f}")
print(f"600 on the old scale is {offset + factor * math.log(50):.1f}"
      f" on the new")
print(f"Gini old {metrics.gini(old, d['bad']):.4f}, "
      f"new {metrics.gini(new, d['bad']):.4f}")
print(f"KS   old {metrics.ks(old, d['bad'])[0]:.4f}, "
      f"new {metrics.ks(new, d['bad'])[0]:.4f}")
p_old = 1 / (1 + np.exp((old - points.OFFSET) / points.FACTOR))
p_new = 1 / (1 + np.exp((new - offset) / factor))
print(f"largest change in an implied bad rate: "
      f"{np.abs(p_old - p_new).max():.1e}")
c, w = mark2.params["bureau_score"], bins["bureau_score"].woe
low = min(w.values())
print("bureau_score points on the new scale:")
print("  " + ", ".join(f"{lab} {round(factor * c * (v - low))}"
                       for lab, v in w.items()))
