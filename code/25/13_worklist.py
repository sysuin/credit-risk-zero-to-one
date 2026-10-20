# Ballast's collections worklist for January 2026: every consumer
# account that fell behind at the December month end, scored for cure
# and given its first action under the policy decided in §25.3.
import fernhill
from ballast import collections as coll
from ballast.config import AS_OF, SEED

con = fernhill.connect()
hist = coll.entries(con, "2016-01-01", "2024-12-31")
model = coll.fit(hist, "cured_3m")
w = coll.worklist(con, AS_OF, model, seed=SEED)
print(f"model fitted on {len(hist):,} entries, 2016-2024")
print(f"fell behind on {AS_OF:%d %B %Y}: {len(w):,} consumer accounts")
print(w["first_action"].value_counts().sort_index().to_string())
print(f"\n{'work order':<11}{'account':<11}{'product':<10}"
      f"{'balance':>10}{'p(cure)':>9}  first action")
show = list(range(5)) + list(range(len(w) - 3, len(w)))
for i in show:
    r = w.iloc[i]
    if i == len(w) - 3:
        print("...")
    print(f"{i + 1:<11}{r['account_id']:<11}{r['product']:<10}"
          f"{r['balance']:>10,.0f}{r['p_cure']:>9.1%}  "
          f"{r['first_action']}")
