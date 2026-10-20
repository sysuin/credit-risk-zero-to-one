# What a never-paid loan costs, what Fernhill's own checks stopped, and
# what Ballast's rules would send the fraud team each month in 2025.
import fernhill
from ballast import data, fraud
from ballast.decision import strategy

con = fernhill.connect()
eco = strategy.loan_economics(con, "personal")
fp = fraud.first_payments(con)
e = fp[fp["never_paid"].notna()].merge(eco, on="account_id",
                                       suffixes=("", "_e"))
e = e[e["open_date"].astype(str) < "2024-01-01"]
never = e["never_paid"].astype(bool)
for name, g in (("never paid", e[never]),
                ("paid something", e[~never])):
    lent, profit = g["amount_cents"].mean(), g["profit"].mean()
    print(f"{name:<15}{len(g):>7,} loans, lent ${lent / 100:>7,.0f} "
          f"each, profit ${profit / 100:>7,.0f}")

raw = data.load_applications(con, unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")]
year = pl["app_date"].astype(str).str[:4]
caught = pl["decline_reason"].astype(object).eq("fraud_check")
print("\nFernhill's fraud-check declines, personal loans, by year")
per_year = [f"{y} {n:>3}"
            for y, n in caught.groupby(year).sum().items()]
for i in range(0, len(per_year), 5):
    print("  " + "    ".join(per_year[i:i + 5]))

y25 = pl[year == "2025"]
f = fraud.flags(y25)
ref = fraud.referred(f)
print(f"\n2025: {len(y25):,} personal applications; Ballast refers "
      f"{ref.sum()} ({ref.sum() / 12:.1f} a month)")
print(f"  of which Fernhill's checks declined "
      f"{int((ref & caught[y25.index]).sum())} of the "
      f"{int(caught[y25.index].sum())} it caught")
print(f"  of the referred, Fernhill approved "
      f"{int((ref & y25['decision'].astype(str).eq('approve')).sum())}")
