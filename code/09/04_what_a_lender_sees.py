# Six ways to treat the unknowns, judged only on what Fernhill can see.
import numpy as np

from ballast.config import SEED
from ballast.scorecard import metrics, reject

f = reject.frames(reject.applicants())
acc, unk, hold = f["accepts"], f["unknown"], f["holdout"]
print(f"training: {len(acc):,} booked with an outcome, "
      f"{len(unk):,} without")
wa = reject.training_set("reweight", acc, unk)["weight"]
print(f"reweight: weights {wa.min():.2f} to {wa.max():.0f}; "
      f"{int((wa > 20).sum())} loans above 20")
print(f"  carry {wa[wa > 20].sum() / wa.sum():.1%} of the weight")
print(f"  effective sample: {wa.sum() ** 2 / (wa ** 2).sum():,.0f} "
      "loans")

rng = np.random.default_rng(SEED)
fits = reject.fit_all(acc, unk, reject.retro(), rng)
bk = hold[hold["known"] & hold["bad"].notna()]
dec = hold[hold["outcome"] == "declined"]
print()
print(f"{'method':<14}{'rows':>8}{'unknowns':>10}{'called bad':>11}"
      f"{'declines':>10}{'Gini':>7}")
base = fits["ignore"]
for m, r in fits.items():
    t = reject.training_set(m, acc, unk, base=base,
                            retro_rows=reject.retro(),
                            rng=np.random.default_rng(SEED))
    inf = t.iloc[len(acc):]
    called = ((inf["bad"] * inf["weight"]).sum() / inf["weight"].sum()
              if len(inf) else float("nan"))
    called_s = "-" if np.isnan(called) else f"{called:.1%}"
    n_unk = len(inf) if m != "fuzzy" else len(inf) // 2
    g = metrics.gini(-r.p_bad(bk), bk["bad"].astype(int))
    print(f"{m:<14}{len(t):>8,}{n_unk:>10,}{called_s:>11}"
          f"{r.p_bad(dec).mean():>10.1%}{g:>7.3f}")
print()
print(f"declines: predicted bad rate, the holdout's {len(dec):,} "
      "declined")
print(f"Gini: on the holdout's {len(bk):,} booked loans, the only "
      "outcomes")
