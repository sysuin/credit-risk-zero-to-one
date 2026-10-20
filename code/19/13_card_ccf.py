# Credit conversion factors for cards: of the limit a cardholder had
# not used a year before default, how much was used by the default?
import fernhill
from ballast.parameters import ead

con = fernhill.connect()
s = ead.ccf_sample(con, "card")
s = s[s["missed0"] == 0]          # up to date a year before
table = ead.fit_ccf(s)
print(f"card defaults with a year's history, up to date then: "
      f"{len(s):,}")
print(f"\n{'used a year out':<16}{'n':>6}{'CCF':>7}{'median':>8}"
      f"{'EAD/limit':>11}{'over limit':>12}")
for band, r in table.iterrows():
    print(f"{band:<16}{r['n']:>6.0f}{r['ccf_raw']:>7.2f}"
          f"{r['ccf_median']:>8.2f}{r['ead_limit']:>11.0%}"
          f"{r['over_limit']:>12.0%}")
print(f"{'all':<16}{len(s):>6}{ead.pooled_ccf(s):>7.2f}")

raised = s["l1"] > s["l0"]
print(f"\nlimit raised in the year before default: {raised.sum()} "
      f"({raised.mean():.1%})")
alt = s.assign(l0=s["l1"])
print(f"CCF against the limit at default instead: "
      f"{ead.pooled_ccf(alt):.2f}")

pred = ead.exposure(s["b0"], s["l0"], table)
print(f"\nbalance a year before  ${s['b0'].sum() / 100:>11,.0f}")
print(f"EAD, actual            ${s['ead'].sum() / 100:>11,.0f}")
print(f"EAD, fitted by band    ${pred.sum() / 100:>11,.0f}")
