# Coarse classing the bureau score, one rule at a time.
from ballast.scorecard import binning, sample, woe

s = sample.build_sample()
train = s[s["fit"]]
x, bad = train["bureau_score"], train["bad"]
spec = sample.BINNING["bureau_score"]
fine = binning.fine_classes("bureau_score", x, bad,
                            missing=spec["missing"],
                            decimals=spec["decimals"])
steps = [
    ("fine classes", fine),
    ("1 every bin 5% or more", binning.coarse_classes(
        fine, x, bad, trend="none", alpha=None, max_bins=99)),
    ("2 + bad rate falls", binning.coarse_classes(
        fine, x, bad, trend="decreasing", alpha=None, max_bins=99)),
    ("3 + neighbours differ", binning.coarse_classes(
        fine, x, bad, trend="decreasing", alpha=0.10, max_bins=99)),
]
print(f"{'rule applied':<26}{'bins':>5}{'turns':>7}{'IV':>8}")
for label, b in steps:
    n = len(b.labels) - 1                     # not counting no file
    print(f"{label:<26}{n:>5}{binning.turns(b, x, bad):>7}"
          f"{woe.information_value(b, x, bad):>8.3f}")

coarse = steps[-1][1]
print()
print(f"{'bin':<10}{'loans':>7}{'share':>7}{'bads':>6}{'bad rate':>10}")
for _, r in woe.woe_table(coarse, x, bad).iterrows():
    print(f"{r['bin']:<10}{r['n']:>7,}{r['share']:>7.1%}"
          f"{r['bads']:>6,}{r['bad_rate']:>10.1%}")
