# How stable is each model: over time, across seeds and samples?
# timeout: 300
import numpy as np

from ballast.config import SEED
from ballast.models import gbm
from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
det = s[s["outcome"] != "indeterminate"].copy()
oot = det["split"] == "out_of_time"


def mark2_score(frame, fitted_on):
    r, bins = model.fit_mark2(fitted_on, binset)
    return points.exact_score(r.params.to_dict(), bins, frame)


def psi(expected, actual):
    """Population stability index over the deciles of `expected`."""
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, 11)))
    e = np.histogram(expected, np.r_[-np.inf, edges[1:-1], np.inf])[0]
    a = np.histogram(actual, np.r_[-np.inf, edges[1:-1], np.inf])[0]
    e, a = e / e.sum(), a / a.sum()
    return float(((a - e) * np.log(a / e)).sum())


base = {"Mark II": mark2_score(det, s),
        "challenger": gbm.fit(s).score(det)}
train = det["split"] == "train"
print("score distribution, training loans against out-of-time:")
for name, sc in base.items():
    print(f"  {name:<11} PSI {psi(sc[train], sc[oot]):.3f}, mean "
          f"{sc[train].mean():.1f} -> {sc[oot].mean():.1f}")

print()
print("the challenger refitted with other seeds:")
print(f"{'seed':>6}{'trees':>7}{'holdout':>9}{'out of time':>13}")
for k in range(6):
    m = gbm.fit(s, seed=SEED + k)
    sc = m.score(det)
    g = [metrics.gini(sc[det["split"] == x], det.loc[
        det["split"] == x, "bad"]) for x in ("holdout", "out_of_time")]
    print(f"{SEED + k:>6}{m.rounds:>7}{g[0]:>9.3f}{g[1]:>13.3f}")

# Refit both on five random nine-tenths of the training loans and
# measure how far each out-of-time applicant's score moves.
rng = np.random.default_rng(SEED)
fit_rows = s.index[s["fit"]]
moves = {name: [] for name in base}
for k in range(5):
    drop = rng.choice(fit_rows, round(0.1 * len(fit_rows)),
                      replace=False)
    sub = s.copy()
    sub.loc[drop, "fit"] = False
    new = {"Mark II": mark2_score(det, sub),
           "challenger": gbm.fit(sub).score(det)}
    for name in base:
        moves[name].append((new[name] - base[name])[oot].abs())
print()
print("refitted on nine-tenths of the training loans, five times:")
print(f"{'':<12}{'median move':>12}{'95th pct':>10}{'over 10 pts':>13}")
for name, m in moves.items():
    a = np.concatenate([v.to_numpy() for v in m])
    print(f"{name:<12}{np.median(a):>12.1f}"
          f"{np.quantile(a, 0.95):>10.1f}{(a > 10).mean():>13.1%}")
