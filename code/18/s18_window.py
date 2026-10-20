# Exercise 18.2: Platt fitted on the development years instead of the
# recent window, both scored on the loans of 2024.
import fernhill
from ballast.parameters import pd as pdm

con = fernhill.connect()
loans = pdm.personal_loans(con)
d = loans.open_month.dt.date
windows = {"Jul 2022-Dec 2023": (d >= pdm.CALIBRATE_FROM)
           & (d <= pdm.CALIBRATE_TO),
           "2016-2022": loans.open_month.dt.year <= 2022}
test = loans[loans.open_month.dt.year == 2024]
print(f"{'fitted on':<20}{'loans':>7}{'rate':>7}{'2024 PD':>9}"
      f"{'log loss':>10}")
for name, sel in windows.items():
    f = loans[sel & loans.seen12]
    cal = pdm.fit_calibration(f.score, f.d12)
    p = cal.pd(test.score)
    print(f"{name:<20}{len(f):>7,}{f.d12.mean():>7.2%}{p.mean():>9.2%}"
          f"{pdm.log_loss(p, test.d12):>10.4f}")
print(f"{'2024, defaulted':<34}{test.d12.mean():>9.2%}")
