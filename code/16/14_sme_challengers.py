# Can the data beat SME-1? Three challengers on the applicants who
# shared their bank accounts, each year scored by a model fitted on
# the other years, compared with SME-1 on the same loans.
import numpy as np
import pandas as pd

import fernhill
from ballast.commercial import sme
from ballast.config import SEED
from ballast.scorecard import metrics as mt
from ballast.scorecard import model as md
from ballast.scorecard import woe

con = fernhill.connect()
s = sme.sample(con)
o = s[s.ob].reset_index(drop=True)
o["sme1"] = o.sme1_score / 20          # SME-1 as one more input
print(f"loans with bank-account data: {len(o):,}, bad {o.bad.sum()}")
print("bad / loans: " + "  ".join(
    f"{y} {g.bad.sum()}/{len(g)}" for y, g in o.groupby("year")
    if y <= 2020))
print("             " + "  ".join(
    f"{y} {g.bad.sum()}/{len(g)}" for y, g in o.groupby("year")
    if y > 2020))


def left_out(fields, extra=()):
    """Log odds of good for each loan, from a model without its
    year: bins, WoE and coefficients all refitted each time."""
    out = pd.Series(np.nan, index=o.index)
    for y in sorted(o.year.unique()):
        fit = o.year != y
        tr = o[fit]
        bins, iv = woe.fit_binset(tr, tr.bad,
                                  {k: sme.SPEC[k] for k in fields})
        keep = [k for k in fields if iv[k] >= 0.02]
        X = woe.encode(o, {k: bins[k] for k in keep})
        for e in extra:
            X[e] = o[e]
        r = md.fit(X[fit], 1 - tr.bad, keep + list(extra))
        out[~fit] = md.log_odds(r, X)[~fit]
    return out


def gini_gap(a, b, bad):
    """How much better score a ranks the loans than score b."""
    return mt.gini(a, bad) - mt.gini(b, bad)


views = {"SME-1": o.sme1_score,
         "data, files only": left_out(sme.FILE_FIELDS),
         "data, files + bank": left_out(sme.FILE_FIELDS
                                        + sme.BANK_FIELDS),
         "SME-1 + bank": left_out(sme.BANK_FIELDS, extra=["sme1"])}
rng = np.random.default_rng(SEED)
print(f"\n{'score':<20}{'Gini':>7}{'vs SME-1':>10}{'interval':>17}"
      f"{'P>0':>6}")
base = mt.gini(o.sme1_score, o.bad)
for label, sc in views.items():
    g = mt.gini(sc, o.bad)
    if label == "SME-1":
        print(f"{label:<20}{g:>7.3f}")
        continue
    d = mt.bootstrap(gini_gap, sc, o.sme1_score, o.bad,
                     n=1000, rng=rng)
    lo, hi = mt.interval(d)
    print(f"{label:<20}{g:>7.3f}{g - base:>+10.3f}{lo:>+9.3f} "
          f"{hi:>+7.3f}{(d > 0).mean():>6.0%}")
a, b = views["data, files + bank"], views["data, files only"]
d = mt.bootstrap(gini_gap, a, b, o.bad, n=1000, rng=rng)
lo, hi = mt.interval(d)
gain = gini_gap(a, b, o.bad)
print(f"bank fields added to the files: {gain:+.3f}"
      f" ({lo:+.3f} to {hi:+.3f})")

bins, iv = woe.fit_binset(o, o.bad, {k: sme.SPEC[k]
                                     for k in sme.BANK_FIELDS})
X = woe.encode(o, bins)
X["sme1"] = o.sme1
r = md.fit(X, 1 - o.bad, sme.BANK_FIELDS + ["sme1"])
print("\nSME-1 + bank on all years: coefficient (p)")
for n, row in md.coefficients(r).drop("const").iterrows():
    info = f"  IV {iv[n]:.3f}" if n in iv else ""
    print(f"  {n:<20}{row.coef:>7.3f} ({row.p:.3f}){info}")
