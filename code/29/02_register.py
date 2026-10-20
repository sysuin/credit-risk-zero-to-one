# Fernhill's model register: owner, materiality, tier, the last
# independent validation (Chapter 23's, where it saved one) and when
# the next is due, from the inventory.
from collections import Counter

from ballast import governance as gv

inv = gv.load_inventory()
for line in gv.register_lines(inv):
    print(line)

live = [e for e in inv if e["tier"] is not None]
print(f"\n{len(inv)} models, {len(live)} live; by tier: "
      + ", ".join(f"{t}: {n}" for t, n in
                  sorted(Counter(e["tier"] for e in live).items())))
no_inherit = Counter(e["own_tier"] for e in live)
print("on materiality and evidence alone: "
      + ", ".join(f"{t}: {n}" for t, n in sorted(no_inherit.items())))
due = Counter(e["due"] for e in live)
print(f"independent validation overdue: {due['overdue']}; "
      f"in use, never validated: {due['now']};\n"
      f"to validate before use: {due['pre-use']}; "
      f"validated and not approved: {due['blocked']}")
done = Counter(e["conclusion"] for e in live if e["validation_date"])
print("validated in 2026: " + ", ".join(f"{n} {c}" for c, n in
                                         sorted(done.items())))
