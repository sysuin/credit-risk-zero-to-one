# What the emergency loans lost, and what the 80% guarantee did:
# every defaulted loan's exposure and what came back, by kind.
import fernhill
from ballast.commercial import sme


def usd(cents: int, width: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.0f}".rjust(width)


con = fernhill.connect()
lent = con.execute("""
    SELECT count(*), sum(amount_cents) FROM accounts
    WHERE product = 'sme_emergency'""").fetchone()
L = sme.emergency_losses(con)
print(f"emergency loans: {lent[0]:,}, ${lent[1] / 100:,.0f} lent")
print(f"in default (first default, 2021 definition): {len(L):,} "
      f"({len(L) / lent[0]:.1%})")
print(f"\n{'':<26}{'loans':>7}{'exposure':>15}{'guarantee':>14}")
for co, g in L.groupby("charged_off"):
    label = "charged off" if co else "in default, not yet"
    print(f"{label:<26}{len(g):>7,}{usd(g.ead_cents.sum(), 15)}"
          f"{usd(g.guarantee.sum(), 14)}")

c = L[L.charged_off]
ead = int(c.ead_cents.sum())
parts = [("guarantee paid", int(c.guarantee.sum())),
         ("collections", int(c.collections_payment.sum())),
         ("collection costs", int(c.cost.sum()))]
print(f"\ncharged-off loans: exposure ${ead / 100:,.0f}")
print(f"  claims paid on {(c.guarantee > 0).sum()} of {len(c)}")
for label, cents in parts:
    print(f"  {label:<24}{usd(cents, 14)}{cents / ead:>9.1%}")
loss = ead - sum(cents for _, cents in parts)
bare = ead - int(c.collections_payment.sum()) - int(c.cost.sum())
print(f"  {'loss to Fernhill':<24}{usd(loss, 14)}{loss / ead:>9.1%}")
print(f"  {'loss with no guarantee':<24}{usd(bare, 14)}"
      f"{bare / ead:>9.1%}")
print(f"\nas a share of all lending: {loss / lent[1]:.2%} with the "
      f"guarantee, {bare / lent[1]:.2%} without")
