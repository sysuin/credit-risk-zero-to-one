# Exercise 13.3: the new-address rule at four thresholds, on booked
# personal loans: what it catches, what it costs, and whom it flags.
import fernhill
from ballast import data, fraud

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
fp = fraud.first_payments(con)
fp = fp[fp["never_paid"].notna()]
b = raw[raw["account_id"].notna()].merge(
    fp[["account_id", "never_paid"]], on="account_id", validate="1:1")
never = b["never_paid"].astype(bool)
addr = b["address_months"].astype(float)
young = b["age"].astype(int) < 30
print(f"{'under':<8}{'flagged':>8}{'caught':>7}{'false/catch':>12}"
      f"{'under-30 of false':>19}")
for k in (3, 6, 9, 12):
    m = addr < k
    c = int((m & never).sum())
    fpos = m & ~never
    print(f"{k:<8}{m.sum():>8,}{c:>7}{fpos.sum() / c:>12.1f}"
          f"{young[fpos].mean():>19.1%}")
print(f"under-30s among all booked loans: {young.mean():.1%}")
