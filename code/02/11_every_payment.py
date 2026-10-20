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
# The emergency business loans of 2020-21 had nothing to pay for
# their first twelve months.
loans["free"] = [12 if p == "sme_emergency" else 0
                 for p in loans["product"]]
loans["ours"] = [monthly_payment(a, r, t, f) for a, r, t, f in
                 zip(loans["amount_cents"], loans["rate_pct"],
                     loans["term"], loans["free"])]
loans["same"] = loans["ours"] == loans["booked"]

print(f"{'product':<15}{'loans':>8}{'to the cent':>13}")
for product, g in loans.groupby("product"):
    print(f"{product:<15}{len(g):>8,}{g['same'].sum():>13,}")
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
both["moved"] = both["asked"] != both["booked"]
print()
print(f"loans with a first instalment so far: {len(both):,}")
same = (~both["moved"]).sum()
print(f"  asked for the booked payment:       {same:,}")
moved = both[both["moved"]]
print(f"  asked for something else:           {len(moved):,}")
for (product, kind), g in moved.groupby(["product", "rate_type"]):
    print(f"    {product} ({kind}): {len(g):,}")

# Those loans' rate had moved before the first payment fell due.
# Recompute at the rate in force then.
moved = moved.assign(again=[
    monthly_payment(a, r, t, f) for a, r, t, f in
    zip(moved["amount_cents"], moved["rate_then"], moved["term"],
        moved["free"])])
print(f"  ...reproduced at the rate in force:"
      f" {(moved['again'] == moved['asked']).sum():,}"
      f" of {len(moved):,}")
