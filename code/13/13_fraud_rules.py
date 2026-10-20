# Fraud rules measured on the loan book: on booked personal loans, what
# each rule flags, how many never-paid loans it catches, at what cost.
import fernhill
from ballast import data, fraud

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
fp = fraud.first_payments(con)
fp = fp[fp["never_paid"].notna()]
b = raw[raw["account_id"].notna()].merge(
    fp[["account_id", "never_paid"]], on="account_id", validate="1:1")
never = b["never_paid"].astype(bool)
f = fraud.flags(b, rules=list(fraud.RULES))
t = fraud.rule_table(f, never)
print(f"{len(b):,} booked personal loans, {never.sum()} never paid")
print(f"{'rule':<26}{'flagged':>8}{'caught':>7}{'share':>7}"
      f"{'false/catch':>12}")
for name, r in t.iterrows():
    print(f"{name:<26}{int(r['flagged']):>8,}{int(r['caught']):>7}"
          f"{r['share_caught']:>7.0%}{r['false_per_catch']:>12.1f}")

young = b["age"].astype(int) < 30
print("\nFlagged loans that paid, share to under-30s "
      f"(all loans: {young.mean():.1%})")
for name in ("young_file", "file_younger_than_person"):
    fpos = f[name] & ~never
    print(f"  {name:<26}{fpos.sum():>6,}{young[fpos].mean():>8.1%}")

d = f[list(fraud.DEFAULT)]
n = d.sum(axis=1)
print(f"\nFlags raised, Ballast's {len(fraud.DEFAULT)} rules")
print(f"{'at least':<10}{'flagged':>8}{'caught':>7}{'share':>7}"
      f"{'false/catch':>12}")
for k in range(1, 5):
    m = n >= k
    c = int((m & never).sum())
    print(f"{k:<10}{m.sum():>8,}{c:>7}{c / never.sum():>7.0%}"
          f"{(m.sum() - c) / c:>12.1f}")
plus = n + f["refused_consent"]
m = plus >= fraud.REFER_AT
c = int((m & never).sum())
print(f"with refused_consent as a sixth rule, at {fraud.REFER_AT}: "
      f"{m.sum():,} flagged, {c} caught")
