# Fernhill's own covenants against its borrowers' accounts: the room
# given at signing, what that practice would give Meridian, and how
# often the room was used up. _book.py loads the accounts.
import numpy as np
import pandas as pd

import fernhill
from _book import accounts, facilities, latest_year, live_years, rates
from _meridian import analysis
from ballast.commercial import structure as st

con = fernhill.connect()
acc, fac = accounts(con), facilities(con)


def tested(d):
    return pd.concat([d, st.breaches(d.debt, d.ebitda, d.interest,
                                     d.cap, d.floor)], axis=1)


# 1. At signing, against the latest accounts Fernhill then held.
fac["fy"] = fac.start_date.map(latest_year)
sign = tested(fac.merge(acc, on=["company_id", "fy"]))
sign = sign[sign.ebitda > 0]
top = sign.cap == sign.cap.max()
rho = sign[["cap", "leverage"]].corr(method="spearman").iloc[0, 1]
print(f"signed on accounts Fernhill held: {len(sign)}")
print(f"  rank correlation of cap and leverage: {rho:+.2f}")
print(f"  median EBITDA headroom: leverage "
      f"{(1 - sign.leverage / sign.cap).median():.0%}, cover "
      f"{(1 - sign.floor / sign.cover).median():.0%}")
for label, g in ((f"at the {sign.cap.max():.2f}x ceiling", sign[top]),
                 ("below it", sign[~top])):
    print(f"  {label:<20}{len(g):>4}   already over the cap "
          f"{g.leverage_breach.mean():>4.0%}")

# 2. The practice, fitted below the ceiling, applied to Meridian.
b, a = np.polyfit(sign[~top].leverage, sign[~top].cap, 1)
k = (sign.floor / sign.cover).median()
m = analysis(con)
r = m["r"]
print(f"\npractice: cap {a:.2f} + {b:.2f} x leverage; floor "
      f"{k:.2f} x cover")
for label, lev, cov in (
        ("Meridian, 2025 accounts", r.loc["leverage", 2025],
         r.loc["interest_cover", 2025]),
        ("Meridian, fully drawn", m["pf"].leverage, m["pf"].cover)):
    cap, floor = round((a + b * lev) * 4) / 4, round(k * cov * 4) / 4
    print(f"  {label:<24}{lev:.2f}x {cov:>5.2f}x -> cap {cap:.2f}x,"
          f" floor {floor:.2f}x")

# 3. Each year's accounts against the covenants live when they came.
cols = ["leverage_breach", "cover_breach", "breach"]
t = tested(live_years(acc, fac.drop(columns="fy")))
cy = (t.groupby(["company_id", "fy", "k"], dropna=False)[cols].any()
      .reset_index())
print(f"\n{'in breach of their own covenants':<32}{'n':>5}"
      f"{'either':>8}{'lev.':>7}{'cover':>7}")
labels = ["defaulters, last accounts",
          "defaulters, one year earlier",
          "defaulters, two years earlier",
          "never defaulted, every year"]
counts = [(cy.k == k).sum() for k in (1, 2, 3)] + [cy.k.isna().sum()]
shares = [rates(cy, c) for c in ["breach"] + cols[:2]]
for i, label in enumerate(labels):
    print(f"{label:<32}{counts[i]:>5}{shares[0][i]:>8.0%}"
          f"{shares[1][i]:>7.0%}{shares[2][i]:>7.0%}")

# 4. The never-defaulted, year by year, beside the policy rate.
h = cy[cy.k.isna() & (cy.fy >= 2017)].groupby("fy")[cols[:2]].mean()
rate = dict(con.execute("""SELECT year(month) - 1, policy_rate_pct
    FROM market_rates WHERE month(month) = 3 ORDER BY 1""").fetchall())
print(f"\n{'never defaulted':<18}" + "".join(
    f"{y % 100:>6}" for y in h.index))
print(f"{'  over the cap':<18}" + "".join(
    f"{v:>6.0%}" for v in h.leverage_breach))
print(f"{'  under the floor':<18}" + "".join(
    f"{v:>6.0%}" for v in h.cover_breach))
print(f"{'  policy rate, Mar':<18}" + "".join(
    f"{rate[y]:>5.2f}%"[-6:] for y in h.index))
