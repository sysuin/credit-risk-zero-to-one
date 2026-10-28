# timeout: 600
# Capital before and after, on one stated illustrative rule, beside
# the share of the pool's expected and tail loss each option sells.
import numpy as np

import fernhill
from ballast import securitisation as sec
from ballast.config import SEED

PREMIUM_PCT = 2.50      # the bank's quote to protect class B, % a year
con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())
cf = sec.simulate(deal, 10_000, 0.10, SEED)
loss = sec.pool_loss(cf, total)
att = sec.attachment()
part = {n: sec.tranche_loss(loss, *att[n]) * (att[n][1] - att[n][0])
        for n in att}                  # each slice's loss, % of pool
tail = loss >= np.quantile(loss, 0.999)
v = sec.RETAIN_VERTICAL
options = [("keep the loans", {"A": 1, "B": 1, "C": 1}),
           ("sell A, keep B and C", {"B": 1, "C": 1}),
           ("sell A and B, keep C", {"C": 1}),
           (f"sell all, keep {v:.0%} of each",
            {"A": v, "B": v, "C": v}),
           ("keep loans, protect B only", {"A": 1, "C": 1})]
k_pct = sec.CAPITAL_PCT
print(f"illustrative rule: capital {k_pct:.0f}% of the pool, borne by "
      f"whoever\nbears its first {k_pct:.0f}% of losses "
      "(Appendix C gives the real rules)\n")
print(f"{'':<30}{'capital':>9}{'share of loss sold':>21}")
print(f"{'option':<30}{'% pool':>9}{'expected':>11}{'1 in 1,000':>12}")
for label, kept in options:
    k = sec.illustrative_capital(kept)
    sold = sum((1 - kept.get(n, 0)) * part[n] for n in att)
    print(f"{label:<30}{k:>9.2%}{sold.mean() / loss.mean():>11.0%}"
          f"{sold[tail].mean() / loss[tail].mean():>12.0%}")

b = dict((n, s) for n, s, _ in sec.notes(deal))["B"]
freed = k_pct / 100 - sec.illustrative_capital(options[4][1])
thick = att["B"][1] - att["B"][0]
cost = freed * total * sec.HURDLE_PCT / 100     # cents a year
print(f"\nprotecting B: premium {PREMIUM_PCT:.2f}% of "
      f"${b / 100:,.0f} = ${b * PREMIUM_PCT / 1e4:,.0f} a year;")
print(f"  B's expected loss {part['B'].mean() / thick:.2%} of B "
      "over the deal;")
print(f"  capital freed ${freed * total / 100:,.0f}, which at a "
      f"{sec.HURDLE_PCT:.0f}% hurdle")
print(f"  would cost ${cost / 100:,.0f} a year to hold")
