# What the 2021 definition changes, account by account, applied to the
# whole decade: materiality, bankruptcy and three months' probation.
import pandas as pd

import fernhill
from ballast import performance as perf


def months_between(start, end):
    """Whole months from one month end to a later one."""
    start, end = pd.to_datetime(start), pd.to_datetime(end)
    years = end.dt.year - start.dt.year
    return years * 12 + end.dt.month - start.dt.month


con = fernhill.connect()
old = perf.default_episodes(con, "dpd90", stitched=False)
new = perf.default_episodes(con, "dod2021", stitched=False)
print(f"{'':<34}{'dpd90':>9}{'dod2021':>9}")
print(f"{'default episodes':<34}{len(old):>9,}{len(new):>9,}")
print(f"{'accounts that ever defaulted':<34}"
      f"{old.account_id.nunique():>9,}{new.account_id.nunique():>9,}")
print(f"{'cures':<34}{old.cure_month.notna().sum():>9,}"
      f"{new.cure_month.notna().sum():>9,}")

# 1. Materiality: 90+ days past due with arrears of $100 or less,
#    or 1% of the balance or less, at the first 90-day month end.
first = perf.first_defaults(old)
imm = con.execute("""
    SELECT p.account_id, p.product, p.arrears_cents
    FROM performance p
    JOIN (SELECT account_id, min(month) AS m FROM performance
          WHERE missed >= 3 GROUP BY 1) f
      ON f.account_id = p.account_id AND f.m = p.month
    WHERE NOT (p.arrears_cents > 10000
               AND p.arrears_cents > 0.01 * p.balance_cents)
    ORDER BY 1""").df()
print(f"\nfirst reached 90 days past due immaterial: {len(imm):,} "
      f"accounts")
by_product = imm["product"].value_counts()
print("  by product: " + ", ".join(
    f"{product} {n}" for product, n in by_product.items()))
# Which of them defaulted later under dod2021, and how much later?
later = perf.first_defaults(new).set_index("account_id")
f90 = first.set_index("account_id")["default_month"]
caught = imm["account_id"][imm["account_id"].isin(later.index)]
lag = months_between(f90[caught], later.loc[caught, "default_month"])
print(f"  later in default under dod2021: {len(caught):,}, "
      f"a median {lag.median():.0f} month(s) later")
for why, n in later.loc[caught, "trigger"].value_counts().items():
    print(f"    triggered by {why}: {n}")
print(f"  never in default under dod2021: "
      f"{len(imm) - len(caught)}")

# 2. Bankruptcy before three missed payments.
bk = new[new["trigger"] == "bankruptcy"]
ever90 = set(first["account_id"])
print(f"\ndod2021 defaults triggered by bankruptcy: {len(bk):,}")
print(f"  on accounts never 90 days past due: "
      f"{(~bk['account_id'].isin(ever90)).sum():,}")
print(f"  cured after probation: {bk['cure_month'].notna().sum():,}")
other = new[new["trigger"] != "bankruptcy"]
print(f"dod2021 cures of other defaults: "
      f"{other['cure_month'].notna().sum():,}")

# 3. Probation: dpd90 defaults that start within three months of
#    the same account's previous cure.
o = old.sort_values(["account_id", "default_month"]).copy()
o["prev_cure"] = o.groupby("account_id")["cure_month"].shift()
gap = months_between(o["prev_cure"], o["default_month"])
print(f"dpd90 re-defaults within 3 months of a cure: "
      f"{int((gap <= 3).sum()):,}")
# Cures followed by a missed payment within the next three months.
cured = old.dropna(subset=["cure_month"])[["account_id", "cure_month"]]
con.register("cured", cured)
slip = con.execute("""
    SELECT count(*) FROM cured c
    WHERE EXISTS (SELECT 1 FROM performance p
                  WHERE p.account_id = c.account_id AND p.missed >= 1
                    AND p.month > c.cure_month
                    AND p.month <= last_day(c.cure_month
                                            + INTERVAL 3 MONTH))
""").fetchone()[0]
print(f"dpd90 cures followed by a missed payment within 3 months: "
      f"{slip:,}")
for name, eps in [("dpd90", old), ("dod2021", new)]:
    for r in eps[eps["account_id"] == "PL0015999"].itertuples():
        print(f"PL0015999 under {name:<8} default {r.default_month}, "
              f"cured {r.cure_month}")
