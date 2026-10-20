# Exercise 16.6: the emergency loans' loss with a smaller guarantee,
# and with collections as good as on unguaranteed SME loans.
import fernhill
from ballast.commercial import sme

con = fernhill.connect()
L = sme.emergency_losses(con)
c = L[L.charged_off]
ead = int(c.ead_cents.sum())
# what collections brought back, net of cost, on what the guarantee
# left: the emergency loans' own record
left = ead - int(c.guarantee.sum())
own = (int(c.collections_payment.sum()) + int(c.cost.sum())) / left
# the same on charged-off SME term loans and overdrafts, whose
# directors' guarantees are counted as recoveries too
back, owed = con.execute("""
    WITH first AS (
        SELECT d.account_id, d.ead_cents FROM defaults d
        JOIN accounts a USING (account_id)
        WHERE a.product IN ('sme_term', 'sme_overdraft')
          AND a.close_reason = 'charged_off'
        QUALIFY row_number() OVER (PARTITION BY d.account_id
                                   ORDER BY d.default_month) = 1)
    SELECT (SELECT sum(r.amount_cents) FROM recoveries r
            WHERE r.account_id IN (SELECT account_id FROM first)
              AND r.kind IN ('collections_payment', 'cost',
                             'guarantee')),
           sum(ead_cents) FROM first""").fetchone()
sme_rate = back / owed
print(f"net recovered on what was left: emergency {own:.1%}, "
      f"ordinary SME {sme_rate:.1%}")
print(f"{'case':<28}{'loss':>14}{'of exposure':>13}")
for label, share, rate in (("as it happened", 0.80, own),
                           ("50% guarantee", 0.50, own),
                           ("80%, SME recoveries", 0.80, sme_rate),
                           ("50%, SME recoveries", 0.50, sme_rate)):
    loss = ead * (1 - share) * (1 - rate)
    print(f"{label:<28}${loss / 100:>13,.0f}{loss / ead:>13.1%}")
