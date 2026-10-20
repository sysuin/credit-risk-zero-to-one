# Months at the address: a zigzag in fine classes, a step in coarse.
from ballast.scorecard import binning, sample, woe

s = sample.build_sample()
train = s[s["fit"]]
x, bad = train["address_months"], train["bad"]
fine, coarse = binning.bin_characteristic(
    "address_months", x, bad, sample.BINNING["address_months"])

c = binning.counts(fine, x, bad)
c["rate"] = c["bads"] / c["n"]
half = (len(c) + 1) // 2
print("fine classes: months at address, loans, bad rate")
for i in range(half):
    left = c.iloc[i]
    line = f"  {left['bin']:<9}{left['n']:>6,}{left['rate']:>7.1%}"
    if i + half < len(c):
        right = c.iloc[i + half]
        line += f"      {right['bin']:<9}{right['n']:>6,}" \
                f"{right['rate']:>7.1%}"
    print(line)
print(f"turns {binning.turns(fine, x, bad)}, "
      f"IV {woe.information_value(fine, x, bad):.3f}")
print()
print("coarse classes:")
for _, r in woe.woe_table(coarse, x, bad).iterrows():
    print(f"  {r['bin']:<9}{r['n']:>6,}{r['bad_rate']:>7.1%}")
print(f"turns {binning.turns(coarse, x, bad)}, "
      f"IV {woe.information_value(coarse, x, bad):.3f}")
