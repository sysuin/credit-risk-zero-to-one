# How Fernhill's personal loans of 2016-2018 ended, and what early
# repayment did to the interest they earned.
import fernhill
from ballast.loanmath import apr, effective_interest_rate, schedule

# One row per loan: its terms, how it ended, how many months it ran,
# and everything it paid back (the final balance is the payoff).
con = fernhill.connect()
loans = con.execute("""
    SELECT a.account_id, year(a.open_date) AS vintage, a.close_reason,
           a.amount_cents, a.rate_pct, a.term_months::INT AS term,
           date_diff('month', a.open_date, a.close_date) AS age,
           sum(p.paid_cents) + arg_max(p.balance_cents, p.month)
               AS received
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'personal' AND year(a.open_date) <= 2018
    GROUP BY ALL ORDER BY a.account_id
""").df()

# One line per vintage: the share of loans that ended each way.
print(f"{'vintage':<9}{'loans':>7}{'prepaid':>9}{'to term':>9}"
      f"{'charged':>9}{'prepaid at':>12}")
for vintage, group in loans.groupby("vintage"):
    count = len(group)
    ended = group["close_reason"].value_counts()
    prepaid = ended.get("prepaid", 0) / count
    to_term = ended.get("repaid", 0) / count
    charged = ended.get("charged_off", 0) / count
    months = group[group["close_reason"] == "prepaid"]["age"].mean()
    print(f"{vintage:<9}{count:>7,}{prepaid:>9.0%}{to_term:>9.0%}"
          f"{charged:>9.0%}{months:>8.1f} mo")
print(f"average term: {loans['term'].mean():.0f} months")

# Interest the prepaid loans earned, against what their schedules
# promised if every one had run to term.
pre = loans[loans["close_reason"] == "prepaid"]
earned = (pre["received"] - pre["amount_cents"]).sum()
promised = 0
for loan in pre.itertuples():
    plan = schedule(loan.amount_cents, loan.rate_pct, loan.term)
    promised = promised + plan["interest"].sum()
print()
print(f"prepaid loans: {len(pre):,}")
print(f"  interest scheduled  ${promised / 100:>14,.0f}")
print(f"  interest earned     ${earned / 100:>14,.0f}"
      f"  ({earned / promised:.0%})")

# The broker loan, repaid in full with its 12th payment: the first
# 12 payments, with the payoff added to the last of them.
plan = schedule(1_280_000, 9.9, 36)
payoff = plan["closing"][11]
early = plan["payment"].tolist()[:12]
early[-1] = early[-1] + payoff
her_apr = apr(1_216_000, early)
eir = effective_interest_rate(1_280_000, early, costs_paid_cents=25_600)
print()
print(f"PL0023628 repaid at month 12: payoff ${payoff / 100:,.2f}")
print(f"  her APR on $12,160 received:      {her_apr:.2f}%")
print(f"  Fernhill's EIR, after commission: {eir:.2f}%")
