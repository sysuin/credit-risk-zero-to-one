# Checking the fraud work against the answer. The truth database knows
# which applications were frauds; this is the one listing that reads it.
import fernhill
from ballast import data, fraud

con = fernhill.connect()
truth = fernhill.connect(truth=True)
is_fraud = truth.execute("SELECT app_id, fraud FROM applicants "
                         "ORDER BY app_id").df()
raw = data.load_applications(con, unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")].merge(
    is_fraud, on="app_id", validate="1:1")
pl["year"] = pl["app_date"].astype(str).str[:4].astype(int)
fr = pl["fraud"].astype(bool)
print(f"Personal applications {len(pl):,}; frauds {fr.sum()}")
for ch in ("branch", "online", "broker"):
    m = pl["channel"].astype(str).eq(ch)
    early, late = m & (pl["year"] < 2021), m & (pl["year"] >= 2021)
    print(f"  {ch:<7} fraud rate 2016-20 {fr[early].mean():.2%}, "
          f"2021-25 {fr[late].mean():.2%}")

fp = fraud.first_payments(con)
fp = fp[fp["never_paid"].notna()].merge(is_fraud, on="app_id")
nv, ff = fp["never_paid"].astype(bool), fp["fraud"].astype(bool)
print(f"\nBooked loans: {ff.sum()} frauds, {nv.sum()} never paid; "
      f"both {int((nv & ff).sum())}")
print(f"  never paid but genuine {int((nv & ~ff).sum())}; fraud that "
      f"paid something {int((ff & ~nv).sum())}")

caught = pl["decline_reason"].astype(object).eq("fraud_check")
ref = fraud.referred(fraud.flags(pl))
print(f"\nFernhill's fraud-check declines {caught.sum()}: frauds "
      f"{int((caught & fr).sum())}")
print(f"Ballast refers {ref.sum():,}: frauds {int((ref & fr).sum())}, "
      f"genuine {int((ref & ~fr).sum())}")
print(f"{'applied':<12}{'frauds':>7}{'Fernhill caught':>17}"
      f"{'Ballast refers':>16}")
for name, a, b in (("2016-Jan 21", "2016", "2021-02"),
                   ("the push", "2021-02", "2022-07"),
                   ("Jul 22-May 23", "2022-07", "2023-06"),
                   ("from Jun 23", "2023-06", "2026")):
    d = pl["app_date"].astype(str)
    m = (d >= a) & (d < b) & fr
    print(f"{name:<12}{m.sum():>7}{caught[m].mean():>17.0%}"
          f"{ref[m].mean():>16.0%}")
