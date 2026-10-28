# What an incurred-loss provision and an expected-loss provision
# would have held on 31 December 2019, against what 2020 then cost.
# timeout: 300
import datetime as dt

import fernhill
import pandas as pd
from ballast import ecl
from ballast import performance as perf

DATE = dt.date(2019, 12, 31)
con = fernhill.connect()
params = ecl.parameters(con, DATE)
r = ecl.run(con, DATE, params)
performing = r[r["stage"] < 3]

# Retail: performing loans that defaulted in 2020. Each one lost its
# exposure at default times its product's loss given default.
eps = perf.default_episodes(con)
d20 = eps[pd.to_datetime(eps["default_month"]).dt.year == 2020]
retail = performing[performing["segment"] == "retail"].merge(
    d20.drop_duplicates("account_id"), left_on="root_id",
    right_on="account_id", suffixes=("", "_d"))
lgd = params["lgd"]["lgd"]
retail_loss = (retail["ead_cents_d"] * retail["product"].map(lgd)).sum()

# Commercial: performing facilities that defaulted in 2020. Each one
# lost what its own workout lost.
workouts = ecl.commercial_lgd(con)
gone = con.execute("""SELECT facility_id FROM facility_months
                      WHERE status = 'defaulted'
                        AND year(month) = 2020""").df()
com = workouts[workouts["facility_id"].isin(gone["facility_id"])
               & workouts["facility_id"].isin(performing["account_id"])]
com_loss = (com["lgd"] * com["ead_cents"]).sum()


def line(name, values):
    cells = "".join(f"{v / 1e8:>12,.1f}" for v in values)
    print(f"{name:<32}{cells}")


def provision(rows):
    # The provision on the chosen rows: retail, then commercial.
    return [r.loc[rows & (r["segment"] == g), "ecl"].sum()
            for g in ("retail", "commercial")]


in_default = r["stage"] == 3
every_row = r["stage"] > 0
print(f"31 December 2019{'':16}{'retail':>12}{'commercial':>12}")
line("book, $m", [r.loc[r["segment"] == g, "balance_cents"].sum()
                  for g in ("retail", "commercial")])
line("incurred: in default only, $m", provision(in_default))
line("expected: IFRS 9, $m", provision(every_row))
line("  of it on performing loans", provision(~in_default))
print("then, in 2020, on loans performing at the date:")
print(f"{'  defaults':<32}{len(retail):>12,}{len(com):>12,}")
line("  their loss, $m", [retail_loss, com_loss])
