# Refit Mark II's characteristics on each sample: do they hold?
from ballast.scorecard import model, sample, woe

s = model.with_file_flag(sample.load_sample())
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
design = model.separate_no_file(binset, train, train["bad"])
chosen = ["bureau_file", "enquiries_6m", "bureau_score",
          "oldest_account_months", "address_months", "dti", "income",
          "revolving_utilisation", "revolving_balance"]
det = s[s["outcome"] != "indeterminate"]
X = woe.encode(det, {n: design[n] for n in chosen})
good = model.target(det)
t = model.stability(X, good, det["split"], chosen)

print(f"{'':<22}{'train':>7}{'hold':>7}{'OOT':>7}{'z hold':>8}"
      f"{'z OOT':>7}")
for name, r in t.iterrows():
    print(f"{name:<22}{r['train_coef']:>7.2f}{r['holdout_coef']:>7.2f}"
          f"{r['out_of_time_coef']:>7.2f}{r['holdout_z']:>+8.1f}"
          f"{r['out_of_time_z']:>+7.1f}")
for split in ("holdout", "out_of_time"):
    negative = t[f"{split}_coef"] <= 0
    neg = t.index[negative & (t.index != "const")]
    bads = int((1 - good[det["split"] == split]).sum())
    print(f"{split}: bads {bads}"
          f", wrong signs on refit: {', '.join(neg) or 'none'}")

# The 2020 payment holidays: fit without those loans.
in_train = det["split"] == "train"
keep = in_train & ~det["holiday"]
with_hol = model.fit(X[in_train], good[in_train], chosen)
without = model.fit(X[keep], good[keep], chosen)
gap = (without.params - with_hol.params).abs()
print(f"without the {int(train['holiday'].sum())} holiday loans: "
      f"largest change {gap.max():.3f} ({gap.idxmax()})")
