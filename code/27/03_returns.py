# A year's return on capital by segment, before running costs: what
# each part of the book earns against the capital it ties up.
import fernhill
from ballast import appetite as ap

con = fernhill.connect()
t = ap.returns(con)
mk = ap.market(con)
cap = ap.capital_now(con)
target = ap.capital_target(cap, ap.stress.load()["summary"])["target"]
m = 1e8
print(f"funding at the cost of funds, {mk['cof']:.2f}%; capital the "
      "larger of economic")
print(f"and regulatory at the {target:.1%} target; hurdle "
      f"{ap.HURDLE:.0%}")
print(f"\n{'segment':<14}{'drawn':>7}{'margin':>7}{'EL':>6}{'EC':>6}"
      f"{'reg':>6}{'return':>7}{'RoC':>7}{'room':>7}")


def line(name, r):
    margin = r.income - r.funding
    print(f"{name:<14}{r.drawn / m:>7,.0f}{margin / m:>7.1f}"
          f"{r.el / m:>6.1f}{r.ec / m:>6.1f}{r.reg / m:>6.1f}"
          f"{r.ret / m:>7.1f}{r.roc:>7.1%}{r.room / m:>7.1f}")


for name, r in t.iterrows():
    line(name, r)
retail = [i for i in t.index if i in ap.RETAIL]
com = [i for i in t.index if i not in ap.RETAIL]
print("-" * 67)
line("retail", ap.total(t, retail))
line("commercial", ap.total(t, com))
line("Fernhill", ap.total(t, t.index))
print("$m a year; margin = interest less funding; return = margin")
print("less EL plus the funding the capital saves; room = what is")
print(f"left for running costs at a {ap.HURDLE:.0%} return")
print(f"capital charged ${ap.total(t, t.index).capital / m:,.0f}m "
      f"against CET1 ${cap['cet1'] / m:,.0f}m")
