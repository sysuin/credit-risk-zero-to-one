# Mark I's PSI month by month, 2019 to mid-2020: against the year
# before each month (as the report did) and against a fixed year.
import json

import pandas as pd

import fernhill
from ballast import monitoring as mon
from ballast.config import ROOT

con = fernhill.connect()
a = con.execute("""
    SELECT app_date, mark1_score FROM applications
    WHERE product = 'personal'
      AND app_date BETWEEN '2017-07-01' AND '2020-12-31'
    ORDER BY app_id""").df()
month = pd.to_datetime(a["app_date"]).dt.to_period("M")
fixed = (month >= "2018-07") & (month <= "2019-06")
roll = mon.monthly_stability(a["mark1_score"], month)
fix = mon.monthly_stability(a["mark1_score"], month, reference=fixed)
t = roll.merge(fix, on=["month", "n", "mean"], suffixes=("", "_f"))
t = t[t["month"] >= "2018-07"].reset_index(drop=True)
show = t[(t["month"] >= "2019-01") & (t["month"] <= "2020-06")]
print("Mark I, personal-loan applicants; "
      "fixed year = Jul 2018-Jun 2019")
print(f"{'month':<9}{'apps':>5}{'mean':>7}{'PSI':>7}{'PSI':>7}"
      f"{'noise':>7}{'shift':>7}{'z':>6}")
print(f"{'':<9}{'':>5}{'':>7}{'rolling':>7}{'fixed':>7}{'99%':>7}"
      f"{'fixed':>7}{'':>6}")
for r in show.itertuples():
    print(f"{r.month:<9}{r.n:>5}{r.mean:>7.1f}{r.psi:>7.3f}"
          f"{r.psi_f:>7.3f}{r.noise:>7.3f}{r.shift_f:>+7.1f}"
          f"{r.z_f:>6.1f}")
over = t[t["psi"] >= mon.PSI_AMBER]
print(f"months at or above {mon.PSI_AMBER:.2f} (rolling), Jul 2018 to "
      f"Dec 2020: {len(over)}")
fig = {k: [round(float(x), 4) for x in t[k]]
       for k in ("psi", "psi_f", "noise")}
fig["month"] = list(t["month"])
(ROOT / "code" / "24" / "02_psi_by_month.json").write_text(
    json.dumps(fig) + "\n")
