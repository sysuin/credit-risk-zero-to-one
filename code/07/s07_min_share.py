# Exercise 2: the bureau score's coarse classes at three minimum sizes.
from ballast.scorecard import binning, sample, woe

s = sample.build_sample()
train = s[s["fit"]]
hold = s[(s["split"] == "holdout") & (s["outcome"] != "indeterminate")]
name = "bureau_score"
spec = sample.BINNING[name]
fine = binning.fine_classes(name, train[name], train["bad"],
                            missing=spec["missing"],
                            decimals=spec["decimals"])
print(f"{'min share':<11}{'bins':>5}{'IV train':>10}{'IV holdout':>12}")
for share in (0.02, 0.05, 0.10):
    b = binning.coarse_classes(fine, train[name], train["bad"],
                               trend="decreasing", min_share=share)
    iv_train = woe.information_value(b, train[name], train["bad"])
    iv_hold = woe.information_value(b, hold[name], hold["bad"])
    print(f"{share:<11.0%}{len(b.labels) - 1:>5}"
          f"{iv_train:>10.3f}{iv_hold:>12.3f}")
    print("   " + "  ".join(b.labels[:-1]))
