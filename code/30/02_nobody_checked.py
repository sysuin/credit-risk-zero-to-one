# Fernhill's version of the unchecked income: loans that passed the
# affordability rule only because of what the applicant said they
# earned.
import fernhill
from ballast import data, fraud
from ballast.decision import policy as pol
from ballast.scorecard import sample

con = fernhill.connect()
apps = data.load_applications(con, unknowns=False)
pl = apps[apps["product"].astype(str).eq("personal")
          & apps["outcome"].astype(str).eq("booked")
          & (apps["app_date"].astype(str) < "2024-07-01")].copy()
out = sample.outcomes(con)
pl = pl.merge(out[out["complete"]][["account_id", "bad"]],
              on="account_id")


def dti_limit(day):
    """The debt-to-income limit of the policy in force that day."""
    return pol.period_of(day)[2]


limit = pl["app_date"].map(dti_limit).astype(float)
checked = pl["income_verified"].astype(bool)
ratio = fraud.income_ratio(pl)


def fails_on(income_cents):
    """Would the loan fail Fernhill's DTI rule on this income?"""
    alt = pl.assign(stated_income_cents=income_cents.round())
    return pol.dti_at_decision(alt) > limit


def show(name, g):
    print(f"  {name:<36}{len(g):>6,}{g['bad'].mean():>8.1%}")


print("Booked personal loans, January 2016 to June 2024")
print(f"  {'':<36}{'loans':>6}{'bad':>8}")
print("Income checked: passed on the stated figure, and on the")
print("verified one?")
# the verified income where there is one, the stated one otherwise
best_income = pl["verified_income_cents"].where(
    checked, pl["stated_income_cents"]).astype(float)
flip = checked & fails_on(best_income)
show("failed on the verified income", pl[flip])
show("passed on both", pl[checked & ~flip])
broker = pl["channel"].astype(str).eq("broker")
med = ratio[broker & checked].median()
print(f"Brokers' checked incomes: median {med:.3f} of stated")
print("Brokers' loans nobody checked, if their incomes were the")
print("same share of stated as the checked ones:")
unchecked = broker & ~checked
fail = unchecked & fails_on(pl["stated_income_cents"].astype(float)
                            * med)
show("would have failed the rule", pl[fail])
show("would still have passed", pl[unchecked & ~fail])
print("bad: 3+ missed payments in the first 12")
