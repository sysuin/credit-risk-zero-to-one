# Where the wrong signs come from: one fact counted eight times.
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
no_file = train["bureau_score"].isna()
bureau = [n for n in short if binset[n].missing == sample.NO_FILE]
print(f"no-file loans in training: {no_file.sum()}, "
      f"bads {train.loc[no_file, 'bad'].sum()}")
print(f"shortlisted columns with a 'no file' bin: {len(bureau)} "
      f"of {len(short)}")

every = model.fit(X, good, short)
w = binset["bureau_score"].woe[sample.NO_FILE]
push = {n: every.params[n] * w for n in bureau}
right = [v for v in push.values() if v < 0]
back = [v for v in push.values() if v > 0]
print()
print("log odds a no-file applicant gets from the bureau columns")
print(f"  {len(right)} right-signed columns  {sum(right):+.3f}")
print(f"  {len(back)} wrong-signed columns  {sum(back):+.3f}")
print(f"  bureau_score alone      {w:+.3f}")
p = model.bad_rate(every, X)
seen = train.loc[no_file, "bad"].mean()
print(f"no-file bad rate: observed {seen:.1%}"
      f", all twelve {p[no_file].mean():.1%}")

hit = model.fit(X[~no_file], good[~no_file], short)
print()
print(f"refitted on the {(~no_file).sum():,} loans with a file:")
for n in model.wrong_signs(every):
    print(f"  {n:<20}{every.params[n]:>+7.3f}  ->  "
          f"{hit.params[n]:>+7.3f}")
print(f"wrong signs among loans with a file: "
      f"{len(model.wrong_signs(hit))}")
