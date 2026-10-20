# Backward elimination on the one-line design: the same answer?
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
X = woe.encode(train, {n: design[n] for n in short + ["bureau_file"]})

cols = list(short)
while True:
    r = model.fit(X, good, cols + ["bureau_file"])
    p = r.pvalues.drop(["const", "bureau_file"])
    worst = p.idxmax()
    if p[worst] < model.ALPHA and not model.wrong_signs(r):
        break
    print(f"drop {worst:<24} p {p[worst]:.3f}")
    cols.remove(worst)
kept = sorted(cols)
print(f"kept {len(kept)} besides bureau_file:")
for i in range(0, len(kept), 3):
    print("  " + ", ".join(kept[i:i + 3]))
same = sorted(cols + ["bureau_file"]) == sorted(model.CHARACTERISTICS)
print(f"same set as forward selection: {same}")
