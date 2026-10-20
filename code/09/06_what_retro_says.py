# Information value with and without the bureau's later evidence.
from ballast.scorecard import reject, sample, woe

f = reject.frames(reject.applicants())
acc, unk = f["accepts"], f["unknown"]
t = reject.training_set("bureau retro", acc, unk,
                        retro_rows=reject.retro())
bins = woe.load_binset(sample.MARK2 / "bins.json")
names = ["bureau_score", "enquiries_6m", "worst_status_24m",
         "revolving_utilisation", "oldest_account_months", "income",
         "address_months", "employment_months", "dti"]
print(f"{'characteristic':<24}{'booked':>8}{'+ retro':>9}{'ratio':>7}")
for n in names:
    a_iv = woe.information_value(bins[n], acc[n],
                                 acc["bad"].astype(int))
    r_iv = woe.information_value(bins[n], t[n], t["bad"].astype(int))
    print(f"{n:<24}{a_iv:>8.3f}{r_iv:>9.3f}{r_iv / a_iv:>7.1f}")
print()
ws = bins["worst_status_24m"]
print("worst status in 24 months: bad rate by bin")
print(f"{'bin':<10}{'booked':>16}{'retro-labelled':>20}")
r = t.iloc[len(acc):]
for lab in ws.labels:
    cells = []
    for g in (acc, r):
        m = (ws.assign(g["worst_status_24m"]) == lab).to_numpy()
        cells.append(f"{g['bad'][m].mean():>6.1%} of {m.sum():>6,}")
    print(f"{lab:<10}{cells[0]:>16}{cells[1]:>20}")
