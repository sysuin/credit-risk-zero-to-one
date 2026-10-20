# Checking the PDs against the answer: the simulator's true 12-month
# PD for every performing personal loan at each December month end.
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fernhill
from ballast import performance as perf
from ballast.parameters import pd as pdm

con = fernhill.connect()
loans = pdm.personal_loans(con)
panel = pdm.account_months(con, loans)
known = panel[panel.complete]
model = pdm.fit_pd_model(known[known.month.dt.year <= 2022])
dec = known[known.month.dt.month == 12].copy()
dec["pit"] = model.pd(dec)
dec["ttc"] = model.pd(dec, u_ahead=pdm.long_run_unemployment(con))

truth = fernhill.connect(truth=True)          # the answer, read once
t = truth.execute("""SELECT account_id, month, pd12 FROM pd12
                     WHERE account_id LIKE 'PL%'
                       AND month(month) = 12""").df()
o = truth.execute("SELECT app_id, pd12_at_open FROM origination").df()
t["month"] = pd.to_datetime(t.month)
# an opening month has two rows (at opening, at the month end); the
# panel starts a month later, so keeping either changes nothing
t = t.drop_duplicates(["account_id", "month"], keep="last")
dec = dec.merge(t, on=["account_id", "month"], how="left",
                validate="1:1")

eps = perf.default_episodes(con, pdm.DEFINITION, products=["personal"])
bk = (eps.trigger == "bankruptcy").mean()
print(f"{len(dec):,} loan-Decembers, all with a true PD; "
      f"{bk:.1%} of the PD's defaults\nare bankruptcies, which the "
      "truth's 90-days event does not count")
print(f"\n{'Dec':<6}{'loans':>7}{'truth':>8}{'PIT':>8}{'TTC':>8}"
      f"{'defaulted':>11}")
by = dec.groupby(dec.month.dt.year)
for y, g in by:
    tag = "  test" if y >= 2023 else ""
    print(f"{y:<6}{len(g):>7,}{g.pd12.mean():>8.2%}{g.pit.mean():>8.2%}"
          f"{g.ttc.mean():>8.2%}{g.y.mean():>11.2%}{tag}")
gap = {k: (by[k].mean() - by.pd12.mean()).abs().mean()
       for k in ("pit", "ttc")}
print(f"Average gap to the truth: PIT {gap['pit']:.2%}, "
      f"TTC {gap['ttc']:.2%}")

dec["band"] = pd.cut(dec.pd12, [0, .01, .02, .05, .1, .3, 1.0])
print(f"\n{'true PD':<13}{'loans':>7}{'truth':>8}{'PIT':>8}"
      f"{'defaulted':>11}")
for b, g in dec.groupby("band", observed=True):
    print(f"{f'{b.left:.0%}-{b.right:.0%}':<13}{len(g):>7,}"
          f"{g.pd12.mean():>8.2%}{g.pit.mean():>8.2%}"
          f"{g.y.mean():>11.2%}")
r = np.corrcoef(np.log(dec.pit), np.log(dec.pd12))[0, 1]
print(f"Correlation of log PIT with log truth: {r:.2f}")

new = loans[loans.open_month.dt.year == 2024].merge(o, on="app_id")
fit = loans[(loans.open_month.dt.date >= pdm.CALIBRATE_FROM)
            & (loans.open_month.dt.date <= pdm.CALIBRATE_TO)]
cal = pdm.fit_calibration(fit.score, fit.d12)
print("\nNew loans of 2024: calibrated PD "
      f"{cal.pd(new.score).mean():.2%}"
      f", truth at opening {new.pd12_at_open.mean():.2%},\n"
      f"defaulted in their first year {new.d12.mean():.2%}")
Path(__file__).with_suffix(".json").write_text(json.dumps({
    "year": [int(y) for y in by.groups],
    "truth": by.pd12.mean().tolist(), "pit": by.pit.mean().tolist(),
    "ttc": by.ttc.mean().tolist(), "seen": by.y.mean().tolist()}))
