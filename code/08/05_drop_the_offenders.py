# The quick fix: select with a sign rule and let the offenders go.
from ballast.scorecard import model, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
good = model.target(train)
short = ["bureau_score", "enquiries_6m", "oldest_account_months",
         "income", "address_months", "revolving_utilisation", "dti",
         "amount_requested", "employment_months", "revolving_balance",
         "worst_status_24m", "open_accounts"]
X = woe.encode(train, {n: binset[n] for n in short})

chosen, steps = model.select(X, good, short)
print(f"{'step':<5}{'added':<24}{'LR':>7}{'p':>9}  refused (sign)")
for i, st in enumerate(steps, 1):
    refused = len(st.wrong_sign)
    print(f"{i:<5}{st.added or '(stop)':<24}{st.lr:>7.1f}"
          f"{st.p:>9.1e}  {refused}")
r = model.fit(X, good, chosen)
print(f"chosen {len(chosen)}; wrong signs {len(model.wrong_signs(r))}")

no_file = train["bureau_score"].isna()
p = model.bad_rate(r, X)
seen = train.loc[no_file, "bad"].mean()
print(f"no-file bad rate: observed {seen:.1%}"
      f", this model {p[no_file].mean():.1%}")
