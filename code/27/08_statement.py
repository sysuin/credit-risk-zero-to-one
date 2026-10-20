# Fernhill's risk appetite statement for 2026: each metric, its
# appetite and tolerance, where the bank stands today, and its status.
import fernhill
from ballast import appetite as ap

con = fernhill.connect()
pos = ap.position(con)
st = ap.statement(pos)


def th(v, unit, higher):
    return (">=" if higher else "<=") + ap.fmt(v, unit)


print(f"{'':<4}{'metric':<28}{'appetite':>9}{'tolerance':>10}"
      f"{'now':>8}  status")
area = None
for _, r in st.iterrows():
    if r.area != area:
        area = r.area
        print(area.upper())
    print(f"{r.id:<4}{r.metric:<28}"
          f"{th(r.appetite, r.unit, r.higher):>9}"
          f"{th(r.tolerance, r.unit, r.higher):>10}"
          f"{ap.fmt(r.value, r.unit):>8}  {r.status}")
k = st.status.value_counts()
print(f"\n{k.get('green', 0)} green, {k.get('amber', 0)} amber, "
      f"{k.get('red', 0)} red of {len(st)}")
print(f"\n{'':<4}{'owner':<8}basis of the thresholds")
for _, r in st.iterrows():
    print(f"{r.id:<4}{r.owner:<8}{r.basis}")
print(f"\nsaved to {ap.save(st, pos)}")
