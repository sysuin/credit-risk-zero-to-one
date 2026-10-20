# Weight of evidence and information value of the bureau score, by hand.
import json
import math

from ballast.scorecard import binning, sample, woe

s = sample.build_sample()
train = s[s["fit"]]
x, bad = train["bureau_score"], train["bad"]
fine, bins = binning.bin_characteristic(
    "bureau_score", x, bad, sample.BINNING["bureau_score"])
c = binning.counts(bins, x, bad)
c["goods"] = c["n"] - c["bads"]
G, B = int(c["goods"].sum()), int(c["bads"].sum())
print(f"all training loans: {G:,} goods, {B:,} bads, "
      f"odds {G / B:.1f} to 1")
print()
print(f"{'bin':<9}{'goods':>7}{'bads':>5}{'odds':>7}{'%good':>7}"
      f"{'%bad':>7}{'WoE':>7}{'IV part':>9}")
iv = 0.0
for _, r in c.iterrows():
    odds = r["goods"] / r["bads"]
    pg, pb = r["goods"] / G, r["bads"] / B
    w = math.log(pg / pb)               # = ln(odds / overall odds)
    part = (pg - pb) * w
    iv += part
    print(f"{r['bin']:<9}{r['goods']:>7,}{r['bads']:>5}{odds:>7.1f}"
          f"{pg:>7.1%}{pb:>7.1%}{w:>7.3f}{part:>9.4f}")
print(f"{'IV':<9}{iv:>58.4f}")
print(f"woe.information_value agrees: "
      f"{woe.information_value(bins, x, bad):.4f}")

t = woe.woe_table(bins, x, bad)
json.dump({"G": G, "B": B, "rows": [
    {"bin": r["bin"], "n": int(r["n"]), "bads": int(r["bads"]),
     "bad_rate": round(float(r["bad_rate"]), 5),
     "woe": round(float(r["woe"]), 4), "iv": round(float(r["iv"]), 4)}
    for _, r in t.iterrows()]},
    open("code/07/09_woe_by_hand.json", "w"), indent=1)
