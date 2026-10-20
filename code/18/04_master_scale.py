# New personal loans placed on Fernhill's master scale by their
# calibrated PD, and each grade's promise checked on the 2024 loans.
import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt
from ballast.parameters import pd as pdm

con = fernhill.connect()
loans = pdm.personal_loans(con)
d = loans.open_month.dt.date
fit = loans[(d >= pdm.CALIBRATE_FROM) & (d <= pdm.CALIBRATE_TO)]
cal = pdm.fit_calibration(fit.score, fit.d12, "platt")
test = loans[loans.open_month.dt.year == 2024].copy()
test["pd"] = cal.pd(test.score)
test["grade"] = rt.grade_of(test["pd"])
lo_s, hi_s = test.score.min(), test.score.max()
print(f"Scores {lo_s}-{hi_s} map to PDs {cal.pd(hi_s):.2%}-"
      f"{cal.pd(lo_s):.2%}: grades {test.grade.min()} to "
      f"{test.grade.max()}")
print(f"\n{'grade':<6}{'scale':>7}{'scores':>10}{'loans':>7}"
      f"{'mean PD':>9}{'def':>5}{'observed':>9}{'95% range':>13}")
for g, s in test.groupby("grade"):
    lo, hi = mg.interval(int(s.d12.sum()), len(s))
    print(f"{g:<6}{rt.pd_of(g):>7.2%}{s.score.min():>6}-"
          f"{s.score.max():<3}{len(s):>7,}{s.pd.mean():>9.2%}"
          f"{s.d12.sum():>5}{s.d12.mean():>9.2%}"
          f"{lo:>7.1%}-{hi:.1%}")
exp = test.grade.map(rt.pd_of).sum()
print(f"{'all':<6}{'':>17}{len(test):>7,}{test.pd.mean():>9.2%}"
      f"{test.d12.sum():>5}{test.d12.mean():>9.2%}")
print(f"\nDefaults expected: {exp:.1f} at the grades' PDs, "
      f"{test.pd.sum():.1f} at the loans'\nown PDs; seen: "
      f"{test.d12.sum()}")
