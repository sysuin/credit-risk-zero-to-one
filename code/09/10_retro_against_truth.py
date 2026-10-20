# How far the bureau's later evidence can be trusted, checked.
from _truth import applicants_with_truth
from ballast.scorecard import reject, sample, woe

a = applicants_with_truth()
f = reject.frames(a)
acc, unk = f["accepts"], f["unknown"]
x = unk.merge(reject.retro(), on="app_id", how="inner")
op = x[x["opened_elsewhere"].astype(bool)]
agree = (op["bad_elsewhere"] == op["truth"]).mean()
print(f"opened elsewhere: {len(op):,}; retro label equals the truth "
      f"for {agree:.1%}")
print()
print(f"{'':<14}{'opened elsewhere':>22}{'did not':>18}")
for out in ("declined", "not_taken_up"):
    g = x[x["outcome"] == out]
    o = g[g["opened_elsewhere"].astype(bool)]
    n = g[~g["opened_elsewhere"].astype(bool)]
    print(f"{out:<14}{len(o):>8,}  true bad {o['truth'].mean():>5.1%}"
          f"{len(n):>7,}  {n['truth'].mean():>5.1%}")
print()
t = reject.training_set("bureau retro", acc, unk,
                        retro_rows=reject.retro())
everyone = a.loc[acc.index.union(unk.index)]
bins = woe.load_binset(sample.MARK2 / "bins.json")
print(f"{'information value':<24}{'booked':>8}{'+ retro':>9}"
      f"{'truth':>8}")
for n in ("bureau_score", "enquiries_6m", "worst_status_24m",
          "revolving_utilisation", "oldest_account_months",
          "employment_months"):
    ivs = [woe.information_value(bins[n], d[n], y.astype(int))
           for d, y in ((acc, acc["bad"]), (t, t["bad"]),
                        (everyone, everyone["truth"]))]
    print(f"{n:<24}{ivs[0]:>8.3f}{ivs[1]:>9.3f}{ivs[2]:>8.3f}")
