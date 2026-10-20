# Exercise 3: the bureau score's training bins, on the holdout.
from ballast.scorecard import binning, sample, woe

s = sample.build_sample()
train = s[s["fit"]]
hold = s[(s["split"] == "holdout") & (s["outcome"] != "indeterminate")]
name = "bureau_score"
_, bins = binning.bin_characteristic(name, train[name], train["bad"],
                                     sample.BINNING[name])
tt = woe.woe_table(bins, train[name], train["bad"])
th = woe.woe_table(bins, hold[name], hold["bad"])
print(f"{'bin':<9}{'train bads':>11}{'WoE':>7}{'IV':>7}"
      f"{'hold bads':>11}{'WoE':>7}{'IV':>7}")
for (_, a), (_, b) in zip(tt.iterrows(), th.iterrows()):
    print(f"{a['bin']:<9}{a['bads']:>11}{a['woe']:>7.2f}{a['iv']:>7.3f}"
          f"{b['bads']:>11}{b['woe']:>7.2f}{b['iv']:>7.3f}")
print(f"{'total':<9}{int(tt['bads'].sum()):>11}{'':>7}"
      f"{tt['iv'].sum():>7.3f}{int(th['bads'].sum()):>11}{'':>7}"
      f"{th['iv'].sum():>7.3f}")
