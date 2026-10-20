# Exercise 28.2: the deal with prepayments 40% slower (about 2023's
# pace) and 50% faster than the decade's curve.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())
print(f"{'prepayments':<14}{'scenario':<10}{'net loss':>10}"
      f"{'to C $':>13}{'A life':>8}")
for k in (0.6, 1.0, 1.5):
    for s in ("base", "severe"):
        cf = sec.project(deal, s, prepay_scale=k)
        w = sec.waterfall(cf, sec.notes(deal))
        t = sec.tranche_table(w)
        net = (cf.defaulted - cf.recovered).sum() / total
        print(f"{f'x {k:.1f}':<14}{s:<10}{net:>10.2%}"
              f"{w['residual'].sum() / 100:>13,.0f}"
              f"{t.loc['A', 'wal']:>8.2f}")
