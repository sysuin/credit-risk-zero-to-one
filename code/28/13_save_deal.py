# The deal summed up and saved for the risk pack: the pool, the
# structure, and each scenario's losses by class.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
deal = sec.inputs(con)
s = sec.summary(deal)
print(f"pool: {s['loans']:,} car loans, ${s['pool_cents'] / 100:,.0f}"
      f" on {s['cut_off']}")
for name, t in s["structure"].items():
    a, d = t["attach_detach"]
    c = t["coupon_pct"]
    print(f"  class {name} {a:>4.0%}-{d:<5.0%}"
          + ("residual" if c is None else f"{c:.2f}%"))
print(f"\n{'scenario':<10}{'defaults':>10}{'net loss':>10}"
      f"{'to C $':>13}{'A, B, C lost $':>18}")
for name, r in s["scenarios"].items():
    lost = ", ".join(f"{v / 100:,.0f}"
                     for v in r["loss_cents"].values())
    print(f"{name:<10}{r['defaults_pct']:>10.2%}"
          f"{r['net_loss_pct']:>10.2%}"
          f"{r['released_cents'] / 100:>13,.0f}{lost:>18}")
print("\nsaved", sec.save(s))
