# The arranger's proposal: three classes of note on the pool, their
# credit enhancement, and the excess spread the pool earns above them.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
deal = sec.inputs(con)
p = deal.loans
total = int(p["balance_cents"].sum())
att = sec.attachment()
cpn = sec.coupons(deal)
print(f"pool ${total / 100:,.0f}; two-year swap {deal.swap_2y_pct:.2f}%"
      f";\nFernhill's cost of funds {deal.cost_of_funds_pct:.2f}%\n")
print(f"{'class':<7}{'size $':>13}{'share':>7}{'attaches':>10}"
      f"{'detaches':>10}{'coupon':>10}")
for t in sec.STRUCTURE:
    a, d = att[t.name]
    c = "residual" if cpn[t.name] is None else f"{cpn[t.name]:.2f}%"
    print(f"{t.name:<7}{t.share * total / 100:>13,.0f}{t.share:>7.0%}"
          f"{a:>10.0%}{d:>10.0%}{c:>10}")

w = p["balance_cents"] / total
pool_rate = float((w * p["rate_pct"]).sum())
cost = sum(t.share * cpn[t.name] for t in sec.STRUCTURE
           if cpn[t.name] is not None)
xs = pool_rate - cost - sec.SERVICING_PCT
print("\nexcess spread at closing, % of the pool a year:")
print(f"  the loans pay             {pool_rate:>6.2f}")
print(f"  less the notes' coupons   {cost:>6.2f}")
print(f"  less servicing            {sec.SERVICING_PCT:>6.2f}")
print(f"  excess spread             {xs:>6.2f}")
print(f"\non the opening balance that is "
      f"${xs * total / 1e4:,.0f} a year")
