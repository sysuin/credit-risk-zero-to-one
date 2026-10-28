# Where the pool's money goes over the life of the deal in the base
# scenario, and what Fernhill would have earned by keeping the loans.
import numpy as np

import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
deal = sec.inputs(con)
cf = sec.project(deal, "base")
notes = sec.notes(deal)
w = sec.waterfall(cf, notes)


def line(label, cents, indent=2):
    print(f"{' ' * indent}{label:<44}{cents / 100:>14,.0f}")


print("base scenario, the whole life of the deal            dollars")
line("the loans pay interest", cf.interest.sum(), 0)
line("and the sold cars bring in", cf.recovered.sum(), 0)
print("which pays, in the waterfall's order")
line("the servicer (Fernhill)", w["fee"].sum())
line("class A interest", w["interest"]["A"].sum())
line("class B interest", w["interest"]["B"].sum())
line("defaulted principal made good", w["pdl_credit"].sum())
line("released to class C", w["residual"].sum())

cof = deal.cost_of_funds_pct
funding = (cf.balance * cof / 1200).sum()
net = (cf.defaulted - cf.recovered).sum()
print("if Fernhill kept the loans")
line("interest", cf.interest.sum())
line(f"less funding at its cost of funds, {cof:.2f}%", -funding)
line("less net losses", -net)
line("margin, before running costs and capital",
     cf.interest.sum() - funding - net)

# Class C's cash each month, discounted at the hurdle rate.
sizes = {name: size for name, size, _ in notes}
c_size = sizes["C"]
c_cash = w["residual"] + w["principal"]["C"]
months = np.arange(1, len(c_cash) + 1)
pv = (c_cash / (1 + sec.HURDLE_PCT / 100) ** (months / 12)).sum()
print(f"class C: face ${c_size / 100:,.0f}; pays back "
      f"${c_cash.sum() / 100:,.0f}\n  worth ${pv / 100:,.0f} "
      f"discounted at {sec.HURDLE_PCT:.0f}% a year, "
      f"{pv / c_size:.1f} times its face")
