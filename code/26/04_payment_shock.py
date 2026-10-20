# The payment shock, measured loan by loan on Fernhill's mortgages,
# and what the supervisor's rate path would do to today's payments.
import numpy as np

import fernhill
from ballast import stress

con = fernhill.connect()
panel = stress.payment_panel(con)
fit = stress.fit_payment_shock(panel)
b, se = fit["params"], fit["bse"]
print(f"Mortgage quarter ends 2017-2024: {fit['n']:,} rows, "
      f"{fit['defaults']} defaults")
print("logit(default in 12 months), coefficient (se):")
for k in ("shock", "missed_1", "missed_2", "u"):
    print(f"  {k:<10}{b[k]:>7.3f} ({se[k]:.3f})")
print(f"a payment 48% above the first: odds x "
      f"{np.exp(b['shock'] * np.log(1.48)):.2f}")

book = con.execute("""
    SELECT p.account_id, p.balance_cents, p.rate_pct, a.rate_type,
           a.payment_cents AS pay0, a.term_months
               - date_diff('month', a.open_date, p.month) AS remaining,
           date_diff('month', p.month, a.open_date
               + to_months(coalesce(a.fixed_months, 0)::INT))
               AS fix_end
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.month = ? AND p.product = 'mortgage'
      AND p.status IN ('up_to_date', 'arrears')
    ORDER BY 1""", [stress.AS_OF]).df()
p0 = stress.start(con)["policy"]
now = stress.annuity(book.balance_cents, book.rate_pct, book.remaining)
print(f"\n{len(book):,} performing mortgages on 31 Dec 2025; payment")
print("against today's, and the odds multiplier on default it brings")
print(f"{'':<22}{'loans':>6}{'median':>8}{'>20% up':>9}{'odds x':>8}")
for name in ("base", "stress_2026"):
    path = stress.paths(con)[name]
    m = int(path.policy.idxmax())
    new = stress.annuity(book.balance_cents, stress.mortgage_rates(
        book, path.policy[m], m + 1, p0), book.remaining)
    up = new / now
    shock = np.log(np.maximum(new / book.pay0, 1)) - np.log(
        np.maximum(now / book.pay0, 1))
    mult = np.exp(b["shock"] * shock)
    print(f"{name} at {path.policy[m]:.2f}% ({path.month[m]:%b %Y})")
    for t, g in book.groupby("rate_type"):
        s = g.index
        print(f"  {t:<20}{len(g):>6}{np.median(up[s]) - 1:>+8.1%}"
              f"{(up[s] > 1.2).mean():>9.1%}"
              f"{np.average(mult[s], weights=g.balance_cents):>8.2f}")
