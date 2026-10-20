# The 12-month PD tested grade by grade: the loans open on 31 December
# 2023 and 2024, each year scored by a model that never saw its
# defaults, against the defaults of the following year.
import fernhill
from _cache import loans
from ballast import validation as vd
from ballast.parameters import pd as pdm
from ballast.scorecard import metrics

con = fernhill.connect()
panel = pdm.account_months(con, loans(con))
bt = vd.pd_backtest(panel, [2024, 2025], pdm.long_run_unemployment(con))
bt["grade"] = pdm.retail_grade(bt["pit"], bt["missed"])
print(f"{len(bt):,} loan-years, {bt['y'].sum()} defaults; one-sided "
      "tests that the\nPD is not too low (small p: too many defaults)")
print(f"{'grade':<7}{'loans':>7}{'PD':>8}{'expected':>10}{'seen':>6}"
      f"{'rate':>8}{'binomial':>10}{'Jeffreys':>10}")
ORDER = [str(g) for g in range(1, 11)] + ["30", "60"]
for g in ORDER:
    x = bt[bt["grade"] == g]
    if len(x) == 0:
        continue
    n, d, p = len(x), int(x["y"].sum()), x["pit"].mean()
    print(f"{g:<7}{n:>7,}{p:>8.2%}{p * n:>10.1f}{d:>6}{d / n:>8.2%}"
          f"{vd.binomial_p(n, d, p):>10.3f}"
          f"{vd.jeffreys_p(n, d, p):>10.3f}")
hl, df, p = metrics.hosmer_lemeshow(bt["pit"], bt["y"])
print(f"All: PD {bt['pit'].mean():.2%}, seen {bt['y'].mean():.2%}; "
      f"Hosmer-Lemeshow\n{hl:.1f} on {df} df, p {p:.3f}; Gini "
      f"{metrics.gini(-bt['pit'], bt['y']):.3f}")
