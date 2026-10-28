# Every candidate characteristic, ranked by information value.
import json

import numpy as np
import pandas as pd

from ballast.config import SEED
from ballast.scorecard import binning, sample, woe

s = sample.build_sample()
train = s[s["fit"]].copy()
hold = s[(s["split"] == "holdout") & (s["outcome"] != "indeterminate")]
hold = hold.copy()
# A characteristic that is pure noise, to see what chance alone scores.
rng = np.random.default_rng(SEED)
train["noise"] = rng.random(len(train))
hold["noise"] = rng.random(len(hold))
spec = dict(sample.BINNING)
spec["noise"] = {"kind": "numeric", "decimals": 2}


def trend_of(bins, bad_rates):
    """Which way the bad rate moves from the first bin to the last."""
    if bins.kind == "categorical":
        return "cat"
    if len(bad_rates) < 2:
        return "-"
    return "rises" if bad_rates[-1] > bad_rates[0] else "falls"


rows, keep = [], {}
for name, sp in spec.items():
    fine, bins = binning.bin_characteristic(
        name, train[name], train["bad"], sp)
    t = woe.woe_table(bins, train[name], train["bad"])
    ordinary = t.iloc[: len(t) - (1 if bins.missing else 0)]
    trend = trend_of(bins, ordinary["bad_rate"].to_numpy())
    rows.append((name, len(ordinary), trend,
                 woe.information_value(fine, train[name], train["bad"]),
                 t["iv"].sum(),
                 woe.information_value(bins, hold[name], hold["bad"])))
    keep[name] = (fine, bins)

print(f"{'characteristic':<22}{'bins':>5}{'trend':>7}{'fine':>7}"
      f"{'coarse':>8}{'holdout':>9}")
for name, n, trend, f, c, h in sorted(rows, key=lambda r: -r[4]):
    print(f"{name:<22}{n:>5}{trend:>7}{f:>7.3f}{c:>8.3f}{h:>9.3f}")

print()
print("bad rate by coarse bin (loans), for four of them:")
for name in ("enquiries_6m", "revolving_utilisation",
             "amount_requested", "age"):
    _, bins = keep[name]
    t = woe.woe_table(bins, train[name], train["bad"])
    line = f"  {name}:"
    for r in t.itertuples():
        cell = f"  {r.bin} {r.bad_rate:.1%} ({r.n:,})"
        if len(line) + len(cell) > 66:
            print(line)
            line = "   "
        line += cell
    print(line)

# For the figures: the ranking, and utilisation's fine and coarse WoE.
fine, bins = keep["revolving_utilisation"]
x, y = train["revolving_utilisation"], train["bad"]
ft, ct = woe.woe_table(fine, x, y), woe.woe_table(bins, x, y)
json.dump({
    "ranking": [{"name": r[0], "fine": round(r[3], 4),
                 "coarse": round(r[4], 4), "holdout": round(r[5], 4)}
                for r in rows],
    "util": {"fine_edges": fine.edges, "fine_woe":
             [round(v, 4) for v in ft["woe"]],
             "coarse_edges": bins.edges, "coarse_woe":
             [round(v, 4) for v in ct["woe"]],
             "max": float(pd.Series(x).quantile(0.995))}},
    open("code/07/10_iv_ranking.json", "w"), indent=1)
