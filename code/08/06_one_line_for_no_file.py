# Say "no file" once, then choose the characteristics again.
from ballast.scorecard import model, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = model.with_file_flag(s[s["fit"]])
good = model.target(train)
short = ["bureau_score", "enquiries_6m", "oldest_account_months",
         "income", "address_months", "revolving_utilisation", "dti",
         "amount_requested", "employment_months", "revolving_balance",
         "worst_status_24m", "open_accounts"]
design = model.separate_no_file(binset, train, train["bad"])
flag = design["bureau_file"].woe
print(f"bureau_file WoE: file {flag['file']:+.3f}, "
      f"no file {flag['no file']:+.3f}")
X = woe.encode(train, {n: design[n] for n in short + ["bureau_file"]})

every = model.fit(X, good, short + ["bureau_file"])
weak = (every.pvalues.drop("const") >= model.ALPHA).sum()
print(f"all 13 together: wrong signs {len(model.wrong_signs(every))}, "
      f"p of 0.05 or more {weak}")

chosen, steps = model.select(X, good, short, force=["bureau_file"])
print()
print(f"{'step':<5}{'added':<24}{'LR':>7}{'p':>9}  refused (sign)")
for i, st in enumerate(steps, 1):
    print(f"{i:<5}{st.added or '(stop)':<24}{st.lr:>7.1f}"
          f"{st.p:>9.1e}  {len(st.wrong_sign)}")

mark2 = model.fit(X, good, chosen)
print()
print(f"{'Mark II':<24}{'coef':>8}{'se':>7}{'p':>8}")
for name, row in model.coefficients(mark2).iterrows():
    print(f"{name:<24}{row['coef']:>8.3f}{row['se']:>7.3f}"
          f"{row['p']:>8.3f}")
no_file = train["bureau_file"] == "no file"
p = model.bad_rate(mark2, X)
seen = train.loc[no_file, "bad"].mean()
print(f"no-file bad rate: observed {seen:.1%}"
      f", Mark II {p[no_file].mean():.1%}")
