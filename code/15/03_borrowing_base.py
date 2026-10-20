# Meridian's borrowing base at the end of 2025, what it leaves to draw
# under a $17m limit, and how it moves with the ineligibles assumed.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
growth = float(sp.ratios(s).loc["revenue_growth", 2025])
limit = int(st.revolver_need(s, 2025, growth=growth).limit)
rec, inv = int(s.loc["receivables", 2025]), int(s.loc["inventory",
                                                     2025])
bb = st.borrowing_base(rec, inv)
labels = [
    ("receivables", "receivables"),
    ("ineligible_receivables",
     f"less ineligible ({st.INELIGIBLE_RECEIVABLES:.0%} assumed)"),
    ("eligible_receivables", "eligible receivables"),
    ("receivables_advance", f"  x {st.ADVANCE_RECEIVABLES:.0%}"),
    ("inventory", "inventory, at cost"),
    ("ineligible_inventory",
     f"less ineligible ({st.INELIGIBLE_INVENTORY:.0%} assumed)"),
    ("eligible_inventory", "eligible inventory"),
    ("inventory_advance", f"  x {st.ADVANCE_INVENTORY:.0%}"),
    ("base", "borrowing base")]
print("$m, end of 2025")
for key, label in labels:
    print(f"  {label:<36}{bb[key] / 1e8:>8.2f}")
drawn = int(s.loc["short_term_debt", 2025])
print(f"\nlimit {limit / 1e8:.2f}; drawn on day one {drawn / 1e8:.2f}"
      f"; free to draw "
      f"{st.availability(bb.base, limit, drawn) / 1e8:.2f}")

print("\nbase as the ineligible receivables change")
for share in (0.05, 0.15, 0.25, 0.35, 0.45):
    b = st.borrowing_base(rec, inv,
                          ineligible_receivables=round(rec * share))
    print(f"  {share:>4.0%} ineligible   base {b.base / 1e8:>6.2f}"
          f"   binds: {'yes' if b.base < limit else 'no'}")
# The share at which the base falls to the limit.
need_r = (limit - bb.inventory_advance) / st.ADVANCE_RECEIVABLES
print(f"  the base falls below the limit above "
      f"{1 - need_r / rec:.1%} ineligible")

coll = bb.eligible_receivables + bb.eligible_inventory
print(f"\neligible collateral at book value {coll / 1e8:.2f}")
print(f"  repaid in full, drawn to the limit, if it fetches "
      f"{limit / coll:.0%}")
print(f"  repaid in full, drawn to the base, if it fetches "
      f"{bb.base / coll:.0%}")
json.dump({"bb": {k: int(v) for k, v in bb.items()},
           "limit": limit, "drawn": drawn},
          open(ROOT / "code/15/03_borrowing_base.json", "w"))
