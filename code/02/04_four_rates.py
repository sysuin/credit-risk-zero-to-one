# One broker loan, four honest rates: nominal, effective, APR and EIR.
import fernhill
from ballast.loanmath import (apr, effective_annual_rate,
                              effective_interest_rate, schedule)

ACCOUNT = "PL0023628"
FEE = 64_000          # hypothetical: the broker's fee, from the advance
COMMISSION = 25_600   # hypothetical: Fernhill's commission to broker

con = fernhill.connect()
amount, term, rate, payment, opened, channel = con.execute("""
    SELECT amount_cents, term_months::INT, rate_pct,
           payment_cents::BIGINT, open_date, channel
    FROM accounts WHERE account_id = ?
""", [ACCOUNT]).fetchone()
print(f"{ACCOUNT}, {channel}, opened {opened}")
print(f"  ${amount / 100:,.0f} over {term} months at {rate}%,"
      f" ${payment / 100:,.2f} a month")

# Fernhill's personal-loan prices that month, best tier first.
prices = con.execute("""
    SELECT DISTINCT offered_rate_pct FROM applications
    WHERE product = 'personal' AND decision = 'approve'
      AND app_date BETWEEN '2025-01-01' AND '2025-01-31'
    ORDER BY 1
""").fetchall()
quoted = []
for price in prices:
    quoted.append(f"{price[0]}%")
print("  prices quoted in January 2025:", ", ".join(quoted))

# What Fernhill's statement for 2025 says. Her balance at the start
# and end of the year, what she paid, how many payments she made,
# and the balances she owed month by month, added up.
opening, closing, paid, months, owed = con.execute("""
    SELECT arg_min(balance_cents, month), arg_max(balance_cents, month),
           sum(paid_cents), count(*) FILTER (WHERE paid_cents > 0),
           sum(balance_cents) FILTER (WHERE month < '2025-12-31')
    FROM performance WHERE account_id = ?
""", [ACCOUNT]).fetchone()
# What she paid that did not reduce the balance was interest.
interest = paid - (opening - closing)
print(f"2025: {months} payments, ${paid / 100:,.2f};"
      f" interest charged ${interest / 100:,.2f}")
print(f"  which is {interest / owed * 12:.2%} a year on what she owed")
print(f"  still owed at the year's end: ${closing / 100:,.2f}")

# Her 36 payments, and the money she actually received.
payments = schedule(amount, rate, term)["payment"].tolist()
received = amount - FEE

# The rates, each worked out on its own line.
effective = effective_annual_rate(rate)
her_apr = apr(received, payments)
her_apr_nominal = apr(received, payments, "nominal")
apr_no_fee = apr(amount, payments)
eir = effective_interest_rate(amount, payments,
                              costs_paid_cents=COMMISSION)
flat = (sum(payments) - amount) / amount / (term / 12) * 100

# Each rate with its label, printed one per line.
rows = [
    ("nominal rate (the advert)", rate),
    ("effective annual rate", effective),
    (f"APR on ${received / 100:,.0f} received", her_apr),
    ("  the same, nominal convention", her_apr_nominal),
    ("APR if there were no fee", apr_no_fee),
    ("Fernhill's EIR, after commission", eir),
    ("flat rate: interest / amount / years", flat),
]
print()
for label, value in rows:
    print(f"{label:<36}{value:>8.2f}%")
