# Exercise 2.1: the ledger of 01_by_hand.py, run for AL0000001.
amount = 24200.00     # dollars lent
rate = 7.9            # percent a year
term = 48             # months
payment = 589.66      # what Fernhill asked for each month

monthly_rate = rate / 100 / 12
balance = amount
for month in range(1, term + 1):
    balance = balance + balance * monthly_rate - payment
print(f"balance after {term} payments: {balance:.4f}")

exact = amount * monthly_rate / (1 - (1 + monthly_rate) ** -term)
print(f"exact payment: {exact:.4f}")
