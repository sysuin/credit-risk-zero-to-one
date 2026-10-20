# The first-payment signature: personal loans whose first payment was
# missed, and those that never paid at all, by channel and period.
import json

import fernhill
from ballast import fraud
from ballast.config import ROOT

con = fernhill.connect()
fp = fraud.first_payments(con)
dates = con.execute("SELECT account_id, app_date FROM applications "
                    "WHERE account_id IS NOT NULL").df()
fp = fp.merge(dates, on="account_id", validate="1:1")
fp = fp[fp["never_paid"].notna()]
fp["never_paid"] = fp["never_paid"].astype(bool)
fp["then_paid"] = fp["first_missed"] & ~fp["never_paid"]
day = fp["app_date"].astype(str)
PERIODS = [("before the push", "2016-01-01", "2021-02-01"),
           ("the push", "2021-02-01", "2022-07-01"),
           ("after the push", "2022-07-01", "2023-06-01"),
           ("from June 2023", "2023-06-01", "2026-01-01")]
CH = ["branch", "online", "broker"]
print(f"{len(fp):,} personal loans with three payments due; "
      f"never paid {fp['never_paid'].sum()}")
fig = {}
for col, title in (("never_paid", "Never paid (first three missed)"),
                   ("then_paid", "First missed, then paid something")):
    print(f"\n{title}")
    print(f"  {'applied':<17}" + "".join(f"{c:>9}" for c in CH)
          + f"{'all':>8}")
    fig[col] = {}
    for name, a, b in PERIODS:
        m = (day >= a) & (day < b)
        r = fp[m].groupby("channel")[col].mean()
        print(f"  {name:<17}" + "".join(f"{r[c]:>9.2%}" for c in CH)
              + f"{fp.loc[m, col].mean():>8.2%}")
        fig[col][name] = {c: round(float(r[c]), 5) for c in CH}
m = (day >= "2021-02-01") & (day < "2022-07-01")
n = fp[m].groupby("channel").size()
print("\nPush loans: " + ", ".join(f"{c} {n[c]:,}" for c in CH))
(ROOT / "code" / "13" / "11_first_payment.json").write_text(
    json.dumps(fig, indent=1) + "\n")
