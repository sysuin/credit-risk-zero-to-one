# timeout: 600
# Exercise 28.1: a thinner structure (A 95%, B 4%, C 1%) against the
# arranger's, on the same simulated lives of the pool.
import fernhill
from ballast import securitisation as sec
from ballast.config import SEED

con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())
cf = sec.simulate(deal, 10_000, 0.10, SEED)
loss = sec.pool_loss(cf, total)
thin = (sec.Tranche("A", 0.95, 0.60), sec.Tranche("B", 0.04, 2.50),
        sec.Tranche("C", 0.01, None))
for label, s in (("arranger's", sec.STRUCTURE), ("thinner", thin)):
    w = sec.waterfall(cf, sec.notes(deal, s))
    att = sec.attachment(s)
    print(f"{label} structure")
    for n in ("C", "B", "A"):
        a, d = att[n]
        alone = sec.tranche_loss(loss, a, d)
        hit = (w["loss"][n] > 100).mean()
        print(f"  {n} {a:>4.0%}-{d:<5.0%} alone: P "
              f"{(alone > 0).mean():.2%} EL {alone.mean():.2%}; "
              f"after: P {hit:.2%}")
    print(f"  released to C: mean "
          f"{w['residual'].sum(-1).mean() / total:.2%} of the pool")
