# The broker loan from Fernhill's side: what it earns and what it costs.
import fernhill
from ballast.loanmath import loan_pnl, schedule

AMOUNT = 1_280_000     # PL0023628: cents lent,
RATE = 9.9             # percent a year,
TERM = 36              # and months
OPEX = 2.5             # illustrative: running costs, % of balance
ANNUAL_PD = 1.0 / 100  # illustrative: chance of default in a year
LGD = 0.80             # illustrative: share of the balance lost
COMMISSION = 25_600    # hypothetical, as in 04_four_rates.py

con = fernhill.connect()
cof = con.execute("""
    SELECT cost_of_funds_pct FROM market_rates
    WHERE month = '2025-01-31'
""").fetchone()[0]
print(f"Fernhill's cost of funds, January 2025: {cof:.2f}%")

# The loan's earnings and costs over its life, in cents.
pnl = loan_pnl(AMOUNT, RATE, TERM, cof, annual_pd=ANNUAL_PD, lgd=LGD,
               opex_pct=OPEX)
balances = schedule(AMOUNT, RATE, TERM)["opening"]
avg = balances.mean()                 # the average balance owed
years = TERM / 12


def show(label, cents):
    """One line: dollars, and a yearly % of the average balance."""
    print(f"{label:<24}{cents / 100:>11,.2f}"
          f"{cents / avg / years:>10.2%}")


print()
print(f"{'over 36 months':<24}{'dollars':>11}{'% a year':>10}")
show("interest earned", pnl["interest"])
show("cost of funds", -pnl["funding"])
show("operating cost", -pnl["opex"])
show("expected loss", -pnl["expected_loss"])
show("net, before commission", pnl["net"])
show("net, after commission", pnl["net"] - COMMISSION)

margin = (pnl["interest"] - pnl["funding"]) / avg / years
print()
print(f"average balance owed: ${avg / 100:,.2f}")
print(f"net interest margin: {margin:.2%}")
