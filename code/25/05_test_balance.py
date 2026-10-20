# The 2024 collections test: who was in each arm, and whether the coin
# made two groups alike before either was phoned or texted.
import numpy as np
from scipy import stats

import fernhill
from ballast import collections as coll

con = fernhill.connect()
rows, accounts = con.execute("""
    SELECT count(*), count(DISTINCT account_id) FROM collections
    WHERE test_arm IS NOT NULL""").fetchone()
t = coll.test_accounts(con)
print(f"test actions {rows:,} on {accounts:,} accounts;\n"
      f"{len(t):,} fell behind afresh in 2024")
call, sms = t[t["call"] == 1], t[t["call"] == 0]
p = stats.binomtest(len(call), len(t), 0.5).pvalue
print(f"call first {len(call):,}   text first {len(sms):,}")
print(f"a fair coin splits this unevenly or worse {p:.0%} of the time")

cons = t["family"].eq("consumer")
checks = {
    "consumer accounts": t["family"].eq("consumer"),
    "  personal": t["product"].eq("personal"),
    "  card": t["product"].eq("card"),
    "  car loan": t["product"].eq("auto"),
    "  mortgage": t["product"].eq("mortgage"),
    "balance ($, log)": t["log_balance"],
    "months on book": t["months_on_book"],
    "bureau score*": t["bureau_v3"].where(cons & t["no_file"].eq(0)),
    "behind in last 12m": t["repeat"],
    "paid part": t["part_paid"],
    "month fell behind": t["month"].dt.month,
}
print(f"\n{'':<20}{'call first':>11}{'text first':>11}"
      f"{'difference':>12}")
print(f"{'':<20}{'':>11}{'':>11}{'(SMD)':>12}")
worst = 0.0
for name, col in checks.items():
    a, b = col[t["call"] == 1].dropna(), col[t["call"] == 0].dropna()
    d = coll.smd(a, b)
    worst = max(worst, abs(d))
    fmt = ".1%" if set(col.dropna().unique()) <= {0, 1} else ".2f"
    print(f"{name:<20}{a.mean():>11{fmt}}{b.mean():>11{fmt}}"
          f"{d:>+12.3f}")
print("* consumer accounts with a bureau file")
print(f"largest standardised difference {worst:.3f}")
bal = np.exp(t["log_balance"]).groupby(t["arm"]).median()
print(f"median balance: call first ${bal['call_first']:,.0f}, "
      f"text first ${bal['sms_first']:,.0f}")
