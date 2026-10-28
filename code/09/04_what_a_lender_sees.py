# Six ways to treat the unknowns, judged only on what Fernhill can see.
import numpy as np

from ballast.config import SEED
from ballast.scorecard import metrics, reject

f = reject.frames(reject.applicants())
acc, unk, hold = f["accepts"], f["unknown"], f["holdout"]
print(f"training: {len(acc):,} booked with an outcome, "
      f"{len(unk):,} without")

# Reweighting: how big the weights get, and what they are worth
w = reject.training_set("reweight", acc, unk)["weight"]
big = w[w > 20]
print(f"reweight: weights {w.min():.2f} to {w.max():.0f}; "
      f"{len(big)} loans above 20")
print(f"  carry {big.sum() / w.sum():.1%} of the weight")
effective = w.sum() ** 2 / (w ** 2).sum()
print(f"  effective sample: {effective:,.0f} loans")

# Fit all six, then judge each on what a lender has
rng = np.random.default_rng(SEED)
fits = reject.fit_all(acc, unk, reject.retro(), rng)
booked = hold[hold["known"] & hold["bad"].notna()]
declined = hold[hold["outcome"] == "declined"]
print()
print(f"{'method':<14}{'rows':>8}{'unknowns':>10}{'called bad':>11}"
      f"{'declines':>10}{'Gini':>7}")
base = fits["ignore"]
for m, r in fits.items():
    t = reject.training_set(m, acc, unk, base=base,
                            retro_rows=reject.retro(),
                            rng=np.random.default_rng(SEED))
    # The rows after the booked loans are the unknowns the method added
    added = t.iloc[len(acc):]
    if len(added):
        bad = (added["bad"] * added["weight"]).sum()
        called = f"{bad / added['weight'].sum():.1%}"
    else:
        called = "-"
    # Fuzzy enters each unknown twice
    n_unknown = len(added) // 2 if m == "fuzzy" else len(added)
    gini = metrics.gini(-r.p_bad(booked), booked["bad"].astype(int))
    print(f"{m:<14}{len(t):>8,}{n_unknown:>10,}{called:>11}"
          f"{r.p_bad(declined).mean():>10.1%}{gini:>7.3f}")
print()
print(f"declines: predicted bad rate, the holdout's {len(declined):,} "
      "declined")
print(f"Gini: on the holdout's {len(booked):,} booked loans, the only "
      "outcomes")
