# Finding the monthly payment twice: by trial, then by formula.
import fernhill


def balance_after(payment, amount, rate, term):
    """What is still owed after `term` months of `payment`."""
    monthly_rate = rate / 100 / 12
    balance = amount
    for month in range(term):
        balance = balance * (1 + monthly_rate) - payment
    return balance


def payment_by_trial(amount, rate, term):
    """Raise the payment a cent at a time until the loan is repaid."""
    payment = 0.00
    tries = 0
    while balance_after(payment, amount, rate, term) > 0:
        payment = payment + 0.01
        tries = tries + 1
    return round(payment, 2), tries


def payment_by_formula(amount, rate, term):
    """The level payment, from the annuity formula."""
    r = rate / 100 / 12
    return amount * r / (1 - (1 + r) ** -term)


found, tries = payment_by_trial(15100.00, 10.9, 60)
print(f"by trial:   ${found:,.2f} after {tries:,} tries")
exact = payment_by_formula(15100.00, 10.9, 60)
print(f"by formula: ${exact:,.4f}, which rounds to ${exact:,.2f}")

# The formula on five of Fernhill's loans, one per product, with
# the payment Fernhill's systems booked beside it.
con = fernhill.connect()
booked = con.execute("""
    SELECT product, amount_cents / 100 AS amount, rate_pct,
           term_months::INT AS term, payment_cents / 100 AS booked
    FROM accounts
    WHERE account_id IN ('PL0000001', 'AL0000001', 'MG0000001',
                         'BT0000001', 'BE0000001')
    ORDER BY product
""").df()
booked["formula"] = [
    round(payment_by_formula(a, r, t), 2)
    for a, r, t in zip(booked["amount"], booked["rate_pct"],
                       booked["term"])
]
print()
print(booked.to_string(index=False))
