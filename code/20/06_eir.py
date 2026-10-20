# The rate IFRS 9 discounts at: each open instalment loan's effective
# interest rate, worked out from its booked terms, against its rate.
# timeout: 300
import fernhill
import numpy as np
from ballast import loanmath

con = fernhill.connect()
df = con.execute("""
    SELECT a.account_id, a.product, a.amount_cents, a.term_months,
           a.rate_pct, a.payment_cents, a.rate_type,
           p.rate_pct AS rate_now
    FROM accounts a JOIN performance p USING (account_id)
    WHERE p.month = DATE '2025-12-31'
      AND p.status IN ('up_to_date', 'arrears', 'default')
      AND a.product IN ('personal', 'auto', 'mortgage', 'sme_term',
                        'sme_emergency')
    ORDER BY a.account_id""").df()
gap = []
for r in df.itertuples():
    free = 12 if r.product == "sme_emergency" else 0
    pays = [0] * free + [r.payment_cents] * int(r.term_months - free)
    eir = loanmath.effective_interest_rate(r.amount_cents, pays)
    gap.append(eir - r.rate_pct)
df["gap"] = np.abs(gap)
print(f"open instalment loans: {len(df):,}")
print("no fees or commissions in Fernhill's records, so the EIR is")
print(f"the rate booked, to within {df['gap'].max():.3f} points "
      "(payments are rounded)")
print(f"\n{'rate type':<21}{'loans':>7}{'booked':>8}{'in force':>10}")
for t, g in df.groupby("rate_type"):
    print(f"{t:<21}{len(g):>7,}{g['rate_pct'].mean():>7.2f}%"
          f"{g['rate_now'].mean():>9.2f}%")
print("mean rates; a floating loan's EIR is the rate in force")
