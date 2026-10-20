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
ok = r[r["stage"] < 3]

# Loss on loans performing at the date that defaulted in 2020: the
# exposure at default times the loss given default (each commercial
# facility's own workout; the product's LGD for retail).
eps = perf.default_episodes(con)
d20 = eps[pd.to_datetime(eps["default_month"]).dt.year == 2020]
ret = ok[ok["segment"] == "retail"].merge(
    d20.drop_duplicates("account_id"), left_on="root_id",
    right_on="account_id", suffixes=("", "_d"))
lgd = params["lgd"]["lgd"]
cl = ecl.commercial_lgd(con)
gone = con.execute("""SELECT facility_id FROM facility_months
                      WHERE status = 'defaulted'
                        AND year(month) = 2020""").df()
com = cl[cl["facility_id"].isin(gone["facility_id"])
         & cl["facility_id"].isin(ok["account_id"])]
lost = {"retail": (ret["ead_cents_d"]
                   * ret["product"].map(lgd)).sum(),
        "commercial": (com["lgd"] * com["ead_cents"]).sum()}
count = {"retail": len(ret), "commercial": len(com)}


def line(name, values):
    cells = "".join(f"{v / 1e8:>12,.1f}" for v in values)
    print(f"{name:<32}{cells}")


s3 = r["stage"] == 3
seg = r["segment"]
print(f"31 December 2019{'':16}{'retail':>12}{'commercial':>12}")
line("book, $m", [r.loc[seg == g, "balance_cents"].sum()
                  for g in ("retail", "commercial")])
line("incurred: in default only, $m",
     [r.loc[s3 & (seg == g), "ecl"].sum()
      for g in ("retail", "commercial")])
line("expected: IFRS 9, $m", [r.loc[seg == g, "ecl"].sum()
                              for g in ("retail", "commercial")])
line("  of it on performing loans", [r.loc[~s3 & (seg == g), "ecl"]
                                     .sum()
                                     for g in ("retail", "commercial")])
print("then, in 2020, on loans performing at the date:")
print(f"{'  defaults':<32}{count['retail']:>12,}"
      f"{count['commercial']:>12,}")
line("  their loss, $m", [lost["retail"], lost["commercial"]])
