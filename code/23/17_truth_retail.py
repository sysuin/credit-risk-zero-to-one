# Checking the validation against the answer: what the simulator knows
# and a bank never can. Mark II-R's promises against every scored
# applicant's true outcome, and the PD backtest against true PDs.
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fernhill
from _cache import loans
from ballast import validation as vd
from ballast.parameters import pd as pdm
from ballast.scorecard import points, reject, sample

con = fernhill.connect()
truth = fernhill.connect(truth=True)            # the answer
# tb: would the applicant have gone bad if Fernhill had lent?
t = truth.execute("""SELECT app_id, bad_12m_if_booked::DOUBLE AS tb
                     FROM origination ORDER BY app_id""").df()
a = reject.applicants()
a = a[~a["policy"] & (a["split"] == "out_of_time")]
a = a.merge(reject.retro(), on="app_id", how="left")
a = a.merge(t, on="app_id", how="left")
worst = sample.load_sample()[["app_id", "worst_missed"]]
a = a.merge(worst, on="app_id", how="left")
# The truth: Fernhill's own outcome where it lent, else the answer
a["truth"] = np.where(a["known"], (a["worst_missed"] >= 3) * 1.0,
                      a["tb"])
a["score"] = reject.load_refit("mark2_retro_ws").scorecard().score(a)
a["promised"] = points.bad_rate_at(a["score"])
seen_else = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(seen_else, a["bad_elsewhere"], np.nan))
a["band"] = pd.cut(a["score"], [0, 540, 560, 580, 600, 620, 999],
                   right=False, labels=["<540", "540-559", "560-579",
                                        "580-599", "600-619", "620+"])
print(f"Applicants past the rules, 2023 to mid-2024: {len(a):,}")
print(f"{'band':<9}{'appl.':>7}{'promised':>10}{'seen':>7}"
      f"{'true':>7}{'true, booked':>14}{'not booked':>12}")
fig = []
for b, g in a.groupby("band", observed=True):
    k = g["known"]
    fig.append({"band": str(b), "promised": g["promised"].mean(),
                "seen": g["seen"].mean(), "truth": g["truth"].mean(),
                "booked": g.loc[k, "truth"].mean(),
                "other": g.loc[~k, "truth"].mean()})
    r = fig[-1]
    print(f"{b:<9}{len(g):>7,}{r['promised']:>10.2%}{r['seen']:>7.2%}"
          f"{r['truth']:>7.2%}{r['booked']:>14.2%}{r['other']:>12.2%}")

panel = pdm.account_months(con, loans(con))
bt = vd.pd_backtest(panel, range(2017, 2026),
                    pdm.long_run_unemployment(con))
p12 = truth.execute("""SELECT account_id, month, pd12 FROM pd12
                       WHERE account_id LIKE 'PL%'
                         AND month(month) = 12""").df()
p12["month"] = pd.to_datetime(p12["month"])
p12 = p12.drop_duplicates(["account_id", "month"], keep="last")
bt = bt.merge(p12, on=["account_id", "month"], how="left",
              validate="1:1")
print(f"\n{'year':<6}{'seen':>6}{'PIT':>8}{'true':>8}{'PIT/true':>10}"
      f"{'test sees':>11}")
for y, g in bt.groupby("year"):
    n, e, tr = len(g), g["pit"].sum(), g["pd12"].sum()
    print(f"{y:<6}{int(g['y'].sum()):>6}{e:>8.1f}{tr:>8.1f}"
          f"{e / tr:>10.2f}{vd.detectable(n, g['pit'].mean()):>10.2f}x")
print("test sees: the true rate, as a multiple of the PD, that a")
print("year's backtest would flag four times in five")
Path(__file__).with_suffix(".json").write_text(json.dumps(fig) + "\n")
