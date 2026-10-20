# What the verified figure would have done to Fernhill's affordability
# rule, and how loans did by what verification found.
import fernhill
from ballast import data, fraud
from ballast.decision import policy as pol

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")].copy()
limit = pl["app_date"].map(lambda d: pol.period_of(d)[2]).astype(float)
ver = pl["income_verified"].astype(bool)
checked = pl.copy()
checked["stated_income_cents"] = pl["verified_income_cents"].where(
    ver, pl["stated_income_cents"])
dti_stated = pol.dti_at_decision(pl)
dti_checked = pol.dti_at_decision(checked)
flips = ver & (dti_stated <= limit) & (dti_checked > limit)
ok = pl["decision"].astype(str).eq("approve")
print(f"Verified personal applications {ver.sum():,}: pass the DTI "
      f"rule on\n  the stated income and fail it on the verified one: "
      f"{flips.sum()}")
print(f"  of those, Fernhill approved {int((flips & ok).sum())}: "
      + ", ".join(f"{c} {n}" for c, n in pl.loc[flips & ok, "channel"]
                  .astype(str).value_counts().items()))

w12 = con.execute("""
    WITH due AS (SELECT account_id, missed, row_number() OVER
                 (PARTITION BY account_id ORDER BY month) AS k
                 FROM performance WHERE product = 'personal'
                 AND scheduled_cents > 0)
    SELECT account_id, max(missed) >= 3 AS bad12,
           max(CASE WHEN k = 3 THEN missed END) >= 3 AS never_paid
    FROM due WHERE k <= 12 GROUP BY 1 ORDER BY 1""").df()
bk = pl[pl["outcome"].astype(str).eq("booked") & ver
        & (pl["app_date"].astype(str) < "2024-07-01")]
bk = bk.assign(flip=flips[bk.index], ratio=fraud.income_ratio(bk))
bk = bk.merge(w12, on="account_id")
print(f"\nVerified loans booked 2016 to mid-2024 ({len(bk):,})")
print(f"  {'':<34}{'loans':>6}{'bad12':>8}{'never':>8}")
for name, m in (("fail DTI on verified income", bk["flip"]),
                ("pass on both", ~bk["flip"])):
    g = bk[m]
    print(f"  {name:<34}{len(g):>6,}{g['bad12'].mean():>8.1%}"
          f"{g['never_paid'].mean():>8.1%}")
for name, a, b in (("verified 70% of stated or less", 0, 0.7),
                   ("70% to 90%", 0.7, 0.9),
                   ("90% to 99.5%", 0.9, 0.995),
                   ("the same or more", 0.995, 99)):
    g = bk[(bk["ratio"] > a) & (bk["ratio"] <= b)]
    print(f"  {name:<34}{len(g):>6,}{g['bad12'].mean():>8.1%}"
          f"{g['never_paid'].mean():>8.1%}")
