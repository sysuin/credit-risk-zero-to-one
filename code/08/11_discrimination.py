# How well Mark II ranks: Gini, AUC and KS on all three samples.
# timeout: 300
import json

import numpy as np

from ballast.config import ROOT, SEED
from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)
det = s[s["outcome"] != "indeterminate"].copy()
det["score"] = card.score(det)

rng = np.random.default_rng(SEED)
print(f"{'sample':<12}{'loans':>7}{'bads':>6}{'AUC':>7}{'Gini':>7}"
      f"{'95% interval':>15}{'KS':>6}{'at':>5}")
curves = {}
for split in model.SPLITS:
    d = det[det["split"] == split]
    sc, bad = d["score"].to_numpy(), d["bad"].to_numpy()
    g = metrics.gini(sc, bad)
    lo, hi = metrics.interval(metrics.bootstrap(
        metrics.gini, sc, bad, n=1000, rng=rng))
    k, at = metrics.ks(sc, bad)
    print(f"{split:<12}{len(d):>7,}{bad.sum():>6}"
          f"{metrics.auc(sc, bad):>7.3f}{g:>7.3f}"
          f"{f'{lo:.3f} to {hi:.3f}':>15}{k:>6.3f}{at:>5.0f}")
    curves[split] = {
        "gini": g, "ks": k, "ks_at": at,
        "roc": metrics.roc_points(sc, bad)[["goods", "bads"]]
        .round(5).to_numpy().tolist(),
        "cap": metrics.cap_points(sc, bad)[["loans", "bads"]]
        .round(5).to_numpy().tolist(),
        "share_bad": float(bad.mean()),
        "cdf": metrics.roc_points(sc, bad).round(5).to_numpy().tolist()}

path = ROOT / "code" / "08" / "11_discrimination.json"
path.write_text(json.dumps(curves) + "\n")
