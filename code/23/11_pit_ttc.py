# Point in time or through the cycle? The saved 12-month model scored
# on every December's performing loans two ways: how each moves with
# the default rate, and how often it regrades a loan that has not
# missed a payment.
import numpy as np

import fernhill
from _cache import loans
from ballast import validation as vd
from ballast.parameters import pd as pdm

con = fernhill.connect()
panel = pdm.account_months(con, loans(con))
dec = panel[(panel["month"].dt.month == 12) & panel["complete"]].copy()
model = pdm.load_pd_model()
dec["pit"] = model.pd(dec)
dec["ttc"] = model.pd(dec, u_ahead=pdm.long_run_unemployment(con))
yr = dec.groupby(dec["month"].dt.year)[["pit", "ttc", "y"]].mean()
print(f"December 2016 to 2024, {len(dec):,} loan-Decembers")
print(f"{'':<22}{'PIT':>8}{'TTC':>8}{'defaulted':>11}")
for name, f in (("highest year", np.max), ("lowest year", np.min)):
    print(f"{name:<22}{f(yr['pit']):>8.2%}{f(yr['ttc']):>8.2%}"
          f"{f(yr['y']):>11.2%}")
# Swing: the highest year's average over the lowest year's
swing = yr.max() / yr.min()
print(f"{'swing, high/low':<22}{swing['pit']:>8.2f}"
      f"{swing['ttc']:>8.2f}{swing['y']:>11.2f}")
corr_pit = np.corrcoef(yr["pit"], yr["y"])[0, 1]
corr_ttc = np.corrcoef(yr["ttc"], yr["y"])[0, 1]
print(f"{'corr. with the rate':<22}{corr_pit:>8.2f}{corr_ttc:>8.2f}")

clean = dec[dec["missed"] == 0].assign(year=dec["month"].dt.year)
for k in ("pit", "ttc"):
    clean[k + "_g"] = pdm.retail_grade(clean[k], 0)
pairs = clean.merge(clean, on="account_id", suffixes=("", "_next"))
pairs = pairs[pairs["year_next"] == pairs["year"] + 1]
print(f"\nUp to date at two December ends in a row ({len(pairs):,}):"
      "\nshare given a different grade the second time")
print(f"{'from':<22}{'PIT':>8}{'TTC':>8}")
for y, x in pairs.groupby("year"):
    moved_pit = vd.migration_share(x["pit_g"], x["pit_g_next"])
    moved_ttc = vd.migration_share(x["ttc_g"], x["ttc_g_next"])
    print(f"Dec {y:<18}{moved_pit:>8.1%}{moved_ttc:>8.1%}")
