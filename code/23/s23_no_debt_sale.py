# Exercise 23.4: the card LGD backtest again, with the debt sales of
# June 2019 and November 2023 taken out of the cash, so that the
# recovery pattern is the collectors' alone.
import pandas as pd

import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
w = w[w["product"] == "card"]
f_all = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
YEARS = range(2019, 2024)


def estimate_at(f, cut):
    then_w = lgd.as_at(w, cut)
    then_f = f[pd.to_datetime(f["month"]) <= cut]
    tq = lgd.recovery_triangle(then_w, then_f, rates, cohort="quarter",
                               as_of=cut)
    rec = lgd.complete(tq, "additive")
    ead = tq.attrs["ead"].loc[rec.index]
    return float(1 - (rec * ead).sum() / ead.sum())


sold = f_all["kind"].eq("debt_sale")
print(f"Card cash flows {len(f_all):,}, of which debt sales "
      f"{sold.sum():,}")
print(f"{'cash':<16}{'':<6}" + "".join(f"{y:>8}" for y in YEARS))
for name, f in (("with sales", f_all), ("without sales", f_all[~sold])):
    now = lgd.estimate(w, f, rates)["by_year"]
    est = [estimate_at(f, pd.Timestamp(y - 1, 12, 31)) for y in YEARS]
    print(f"{name:<16}{'est.':<6}" + "".join(f"{e:>8.1%}" for e in est))
    print(f"{'':<16}{'now':<6}"
          + "".join(f"{now[str(y)]:>8.1%}" for y in YEARS))
