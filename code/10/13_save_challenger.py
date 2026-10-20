# Fit the challenger, save it beside Mark II, and load it back.
import numpy as np

from ballast.models import gbm, reasons
from ballast.scorecard import metrics, sample

s = sample.load_sample()
model = gbm.fit(s)
det = s[s["outcome"] != "indeterminate"]
sc = model.score(det)
gini = {k: round(metrics.gini(sc[det["split"] == k],
                              det.loc[det["split"] == k, "bad"]), 4)
        for k in ("train", "holdout", "out_of_time")}
for f in gbm.save(model, extra={"gini": gini}):
    print(f"wrote {f.relative_to(gbm.CHALLENGER.parents[2])}  "
          f"({f.stat().st_size:,} bytes)")

back = gbm.load()
same = np.array_equal(back.score(s).to_numpy(),
                      model.score(s).to_numpy())
print()
print(f"reloaded: {back.rounds} trees, {len(back.features)} "
      f"characteristics, {len(back.monotone)} constrained")
print(f"every one of {len(s):,} loans scores the same: {same}")
pts = reasons.in_points(back, s)
gap = (pts.sum(axis=1) - back.score(s)).abs().max()
print(f"contributions add up to every score (within 1e-9): "
      f"{gap < 1e-9}")
print("Gini saved: " + ", ".join(
    f"{k} {v:.3f}" for k, v in gini.items()))
