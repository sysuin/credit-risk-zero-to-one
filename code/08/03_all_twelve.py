# Fit the whole shortlist at once, and read the signs.
from ballast.scorecard import model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
good = model.target(train)
short = ["bureau_score", "enquiries_6m", "oldest_account_months",
         "income", "address_months", "revolving_utilisation", "dti",
         "amount_requested", "employment_months", "revolving_balance",
         "worst_status_24m", "open_accounts"]
X = woe.encode(train, {n: binset[n] for n in short})
r = model.fit(X, good, short)

t = model.coefficients(r)
print(f"{'characteristic':<24}{'coef':>8}{'se':>7}{'p':>8}  sign")
for name, row in t.iterrows():
    flag = "" if row["sign_ok"] else "WRONG"
    print(f"{name:<24}{row['coef']:>8.3f}{row['se']:>7.3f}"
          f"{row['p']:>8.3f}  {flag}")
print(f"wrong signs: {len(model.wrong_signs(r))} of {len(short)}")

# What those three lines would pay, on the scale of section 8.3.
card = points.scorecard(r.params.to_dict(), binset)
print()
for name in model.wrong_signs(r):
    rows = card.table[card.table["characteristic"] == name]
    cells = "  ".join(f"{b} {p:>2}" for b, p in
                      zip(rows["bin"], rows["points"]))
    print(f"{name:<18}{cells}")
