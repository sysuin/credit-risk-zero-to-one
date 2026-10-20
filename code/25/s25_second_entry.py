# Exercise 3: accounts that fell behind afresh twice in 2024; the
# effect of phoning first on the first entry and on the second.
import fernhill
from ballast import collections as coll

con = fernhill.connect()
t = coll.test_accounts(con)
e = coll.entries(con, coll.TEST_START, coll.TEST_END,
                 products=tuple(coll.FAMILY))
e = e.merge(t[["root_id", "arm"]], on="root_id")
e = e.sort_values(["root_id", "month"])
e["n"] = e.groupby("root_id").cumcount() + 1
twice = e[e.groupby("root_id")["n"].transform("max") >= 2]
print(f"accounts falling behind afresh twice or more in 2024: "
      f"{twice['root_id'].nunique():,}")
for k in (1, 2):
    g = twice[twice["n"] == k]
    a, b = g[g["arm"] == "call_first"], g[g["arm"] == "sms_first"]
    d, lo, hi = coll.diff_in_proportions(
        a["cured_1m"].sum(), len(a), b["cured_1m"].sum(), len(b))
    print(f"entry {k}: call {a['cured_1m'].mean():.1%} ({len(a)}), "
          f"text {b['cured_1m'].mean():.1%} ({len(b)}), "
          f"{100 * d:+.1f} ({100 * lo:+.1f} to {100 * hi:+.1f})")
