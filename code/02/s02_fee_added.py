# Exercise 2.3: the broker's fee added to the loan, not taken from it.
from ballast.loanmath import apr, schedule


def show(label, borrowed, received):
    """Print the payment and the APR for one way of paying the fee."""
    loan = schedule(borrowed, 9.9, 36)
    payment = loan["payment"][0] / 100
    rate = apr(received, loan["payment"].tolist())
    print(f"{label:<22} payment ${payment:,.2f}  APR {rate:.2f}%")


show("fee from the advance", 1_280_000, 1_216_000)
show("fee added to the loan", 1_344_000, 1_280_000)
