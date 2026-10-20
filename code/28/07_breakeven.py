# How many times the scenario's default rates each class can take
# before it loses a dollar: the break-even multiples.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())


def defaults_at(k, scenario):
    cf = sec.project(deal, scenario, hazard_scale=k)
    net = (cf.defaulted - cf.recovered).sum() / total
    return cf.defaulted.sum() / total, net


print(f"{'':<8}{'multiple of':>14}{'defaults':>11}{'net loss':>11}")
print(f"{'class':<8}{'the hazards':>14}{'% of pool':>11}"
      f"{'% of pool':>11}")
for s in ("base", "severe"):
    d, net = defaults_at(1.0, s)
    print(f"{s + ', as published':<22}{d:>11.2%}{net:>11.2%}")
    for n in ("C", "B", "A"):
        k = sec.breakeven(deal, n, s)
        d, net = defaults_at(k, s)
        print(f"  {n:<6}{k:>14.1f}{d:>11.2%}{net:>11.2%}")
