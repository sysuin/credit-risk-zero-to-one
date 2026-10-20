# LGD backtested out of time: the estimate Ballast's method would have
# given at each year end, from the workouts as they stood then, against
# the LGD of the next year's defaults as they stand now.
import json
from pathlib import Path

import pandas as pd

import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
PRODUCTS = ("card", "personal", "auto", "sme_term")
YEARS = range(2019, 2024)


def estimate_at(wp, cut):
    """The additive-completed LGD, as an analyst could have computed
    it on `cut` from the workouts and cash seen by then."""
    then_w = lgd.as_at(wp, cut)
    then_f = f[pd.to_datetime(f["month"]) <= cut]
    tq = lgd.recovery_triangle(then_w, then_f, rates, cohort="quarter",
                               as_of=cut)
    rec = lgd.complete(tq, "additive")
    ead = tq.attrs["ead"].loc[rec.index]
    return float(1 - (rec * ead).sum() / ead.sum())


print("Estimate at the end of the year before, and the year's defaults")
print("as they stand now (unfinished workouts completed the same way)")
print(f"{'product':<10}{'':<6}" + "".join(f"{y:>8}" for y in YEARS)
      + f"{'error':>8}")
fig = {}
for p in PRODUCTS:
    wp = w[w["product"] == p]
    now = lgd.estimate(wp, f, rates)["by_year"]
    est = [estimate_at(wp, pd.Timestamp(y - 1, 12, 31)) for y in YEARS]
    act = [now[str(y)] for y in YEARS]
    n = [int((wp["default_month"].dt.year == y).sum()) for y in YEARS]
    err = sum(e - a for e, a in zip(est, act)) / len(est)
    print(f"{p:<10}{'est.':<6}" + "".join(f"{e:>8.1%}" for e in est)
          + f"{err:>+8.1%}")
    print(f"{'':<10}{'now':<6}" + "".join(f"{a:>8.1%}" for a in act))
    print(f"{'':<10}{'n':<6}" + "".join(f"{x:>8,}" for x in n))
    fig[p] = {"years": list(YEARS), "est": est, "act": act}
Path(__file__).with_suffix(".json").write_text(json.dumps(fig) + "\n")
