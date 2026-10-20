# Exercise 18.1: Chapter 10's challenger as a probability, before and
# after a Platt recalibration on the same recent loans.
import numpy as np

import fernhill
from ballast import data
from ballast.decision import engine
from ballast.models import gbm
from ballast.parameters import pd as pdm

con = fernhill.connect()
loans = pdm.personal_loans(con)
raw = data.load_applications(con, unknowns=False)
apps = raw[raw.app_id.astype(str).isin(loans.app_id)]
chars = engine.prepare(apps)
p = gbm.load().p_bad(chars)
loans = loans.merge(chars[["app_id"]].assign(p_raw=np.asarray(p)),
                    on="app_id")
loans["lo"] = np.log(loans.p_raw / (1 - loans.p_raw))
d = loans.open_month.dt.date
fit = loans[(d >= pdm.CALIBRATE_FROM) & (d <= pdm.CALIBRATE_TO)]
test = loans[loans.open_month.dt.year == 2024]
cal = pdm.fit_calibration(fit.lo, fit.d12)
print(f"Platt on the challenger's log odds: {cal.a:.3f} + "
      f"{cal.b:.3f} x log odds")
print(f"{'2024 loans':<22}{'mean PD':>9}{'log loss':>10}")
for name, q in (("challenger as is", test.p_raw),
                ("recalibrated", cal.pd(test.lo))):
    print(f"{name:<22}{np.mean(q):>9.2%}"
          f"{pdm.log_loss(q, test.d12):>10.4f}")
print(f"{'defaulted':<22}{test.d12.mean():>9.2%}")
