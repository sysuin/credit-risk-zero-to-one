# timeout: 900
# The same pool under four assumptions about how much its borrowers'
# fortunes move together: the tail, and the classes' losses alone.
import numpy as np

import fernhill
from ballast import securitisation as sec
from ballast.config import SEED

SIMS = 5_000
con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())
att = sec.attachment()
print(f"{SIMS:,} lives each; pool loss % and the classes' losses alone")
print(f"{'':<6}{'pool loss':>21}{'C':>10}{'class B':>18}")
print(f"{'rho':<6}{'mean':>7}{'1 in 1,000':>14}{'EL':>10}"
      f"{'P(loss)':>10}{'EL':>8}{'A EL':>8}")
for rho in (0.05, 0.10, 0.20, 0.30):
    cf = sec.simulate(deal, SIMS, rho, SEED)
    loss = sec.pool_loss(cf, total)
    c = sec.tranche_loss(loss, *att["C"])
    b = sec.tranche_loss(loss, *att["B"])
    a = sec.tranche_loss(loss, *att["A"])
    print(f"{rho:<6.2f}{loss.mean():>7.2%}"
          f"{np.quantile(loss, 0.999):>14.2%}{c.mean():>10.1%}"
          f"{(b > 0).mean():>10.2%}{b.mean():>8.2%}{a.mean():>8.3%}")
