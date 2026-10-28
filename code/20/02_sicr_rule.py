# Choosing the threshold for a significant increase in credit risk:
# stage the book a year back several ways and see who defaulted next.
# timeout: 300
import datetime as dt

import fernhill
import numpy as np
import pandas as pd
from ballast import ecl
from ballast import performance as perf

con = fernhill.connect()
eps = perf.default_episodes(con)
dm = pd.to_datetime(eps["default_month"])
print(f"{'date':<11}{'rule':<10}{'stage 2':>8}"
      f"{'defaulted next year':>27}{'caught':>8}")
print(f"{'':<21}{'share':>8}{'stage 2':>9}{'added':>9}{'stage 1':>9}")
for date in (dt.date(2023, 12, 31), dt.date(2024, 12, 31)):
    r = ecl.run(con, date, ecl.parameters(con, date))

    # Who defaulted in the next twelve months: retail accounts from
    # their default episodes, commercial facilities from their status.
    t0 = pd.Timestamp(date)
    t1 = t0 + pd.DateOffset(months=12)
    retail_next = set(eps["account_id"][(dm > t0) & (dm <= t1)])
    commercial_next = {x[0] for x in con.execute(
        """SELECT facility_id FROM facility_months
           WHERE status = 'defaulted' AND month > ? AND month <= ?""",
        [date, t1.date()]).fetchall()}
    defaulted = np.where(r["segment"] == "retail",
                         r["root_id"].isin(retail_next),
                         r["account_id"].isin(commercial_next))

    # Restage only the accounts not already in default.
    live = (r["stage"] < 3).to_numpy()
    book = r[live]
    dflt = defaulted[live]
    # An infinite ratio turns the PD test off: the backstops alone.
    backstop = (ecl.stage(book, np.inf)["stage"] == 2).to_numpy()

    for name, ratio in [("1.5x", 1.5), ("2x", 2.0), ("3x", 3.0),
                        ("backstops", np.inf)]:
        stage = ecl.stage(book, ratio, ecl.SICR_POINTS)["stage"]
        two = (stage == 2).to_numpy()
        added = two & ~backstop
        if added.any():
            added_rate = f"{dflt[added].mean():>9.1%}"
        else:
            added_rate = f"{'-':>9}"
        caught = dflt[two].sum() / dflt.sum()
        print(f"{str(date):<11}{name:<10}{two.mean():>8.1%}"
              f"{dflt[two].mean():>9.1%}{added_rate}"
              f"{dflt[~two].mean():>9.1%}{caught:>8.0%}")
print("rule: 12-month PD at least that multiple of origination's and")
print("one point higher, plus the backstops (30 days past due, a")
print("year after a cure, the commercial watchlist); added: accounts")
print("the PD test adds to the backstops; caught: share of next")
print("year's defaults already in stage 2")
