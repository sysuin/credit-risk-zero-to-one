# Through-the-cycle PDs for every exposure: the arrears pools' long-run
# rates, then each product's average PD against Chapter 20's
# point-in-time PD for the same accounts.
import fernhill
from ballast import capital

con = fernhill.connect()
pools = capital.arrears_pools(con)
print("defaulted within 12 months, quarter ends 2016-2024")
print(f"{'product':<15}{'1 behind':>16}{'2 behind':>16}")
for p, g in pools.groupby("product"):
    cells = [f"{r.rate:>7.1%} of {r.n:>5,}" for r in g.itertuples()]
    print(f"{p:<15}" + "".join(f"{c:>16}" for c in cells))

b = capital.book(con)
b["pd"] = capital.ttc_pd(con, b, pools)
b["floored"] = capital.floor_pd(b["pd"], b.cls) > b["pd"]
pit = capital.provisions().set_index("account_id")["pd12"]
b["pit"] = b.account_id.map(pit)
ok = b[~b.in_default & (b.drawn_cents > 0)]
w = ok.drawn_cents
print("\nperforming exposures, PD weighted by balance")
print(f"{'product':<20}{'TTC':>7}{'PIT':>7}{'at floor':>10}")
for p, g in ok.groupby("product"):
    gw = g.drawn_cents
    print(f"{p:<20}{(g['pd'] * gw).sum() / gw.sum():>7.2%}"
          f"{(g.pit * gw).sum() / gw.sum():>7.2%}"
          f"{g.floored.sum():>10,}")
print(f"{'all':<20}{(ok['pd'] * w).sum() / w.sum():>7.2%}"
      f"{(ok.pit * w).sum() / w.sum():>7.2%}{ok.floored.sum():>10,}")
print("PIT: Chapter 20's 12-month PD, weighted across its scenarios")
