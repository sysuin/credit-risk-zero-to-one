# Ballast's payment against every instalment loan Fernhill has booked.
import fernhill
from ballast.loanmath import monthly_payment

con = fernhill.connect()
loans = con.execute("""
    SELECT account_id, product, rate_type, amount_cents, rate_pct,
           term_months::INT AS term, payment_cents::BIGINT AS booked
    FROM accounts
    WHERE payment_cents IS NOT NULL
    ORDER BY account_id
""").df()

# Ballast's payment for each loan. The emergency business loans of
# 2020-21 had nothing to pay for their first twelve months.
free_months = []
ours = []
for loan in loans.itertuples():
    if loan.product == "sme_emergency":
        free = 12
    else:
        free = 0
    free_months.append(free)
    ours.append(monthly_payment(loan.amount_cents, loan.rate_pct,
                                loan.term, free))
loans["free"] = free_months
loans["ours"] = ours
loans["same"] = loans["ours"] == loans["booked"]

print(f"{'product':<15}{'loans':>8}{'to the cent':>13}")
for product, group in loans.groupby("product"):
    print(f"{product:<15}{len(group):>8,}{group['same'].sum():>13,}")
print(f"{'all':<15}{len(loans):>8,}{loans['same'].sum():>13,}")

# The first instalment each borrower was actually asked for, from
# the monthly records, against the payment booked at opening.
first = con.execute("""
    SELECT account_id, arg_min(scheduled_cents, month) AS asked,
           arg_min(rate_pct, month) AS rate_then
    FROM performance
    WHERE scheduled_cents > 0
      AND account_id IN (SELECT account_id FROM accounts
                         WHERE payment_cents IS NOT NULL)
    GROUP BY account_id
""").df()
both = loans.merge(first, on="account_id")
moved = both[both["asked"] != both["booked"]]
same = len(both) - len(moved)
print()
print(f"loans with a first instalment so far: {len(both):,}")
print(f"  asked for the booked payment:       {same:,}")
print(f"  asked for something else:           {len(moved):,}")
for (product, kind), group in moved.groupby(["product", "rate_type"]):
    print(f"    {product} ({kind}): {len(group):,}")

# Those loans' rate had moved before the first payment fell due.
# Recompute at the rate in force then.
matched = 0
for loan in moved.itertuples():
    again = monthly_payment(loan.amount_cents, loan.rate_then,
                            loan.term, loan.free)
    if again == loan.asked:
        matched = matched + 1
print(f"  ...reproduced at the rate in force:"
      f" {matched:,} of {len(moved):,}")
