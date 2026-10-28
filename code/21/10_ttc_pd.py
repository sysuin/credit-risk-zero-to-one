# Through-the-cycle PDs for every exposure: the arrears pools' long-run
# rates, then each product's average PD against Chapter 20's
# point-in-time PD for the same accounts.
import fernhill
from ballast import capital


def weighted(values, weights):
    return (values * weights).sum() / weights.sum()


con = fernhill.connect()
pools = capital.arrears_pools(con)
print("defaulted within 12 months, quarter ends 2016-2024")
print(f"{'product':<15}{'1 behind':>16}{'2 behind':>16}")
for product, rows in pools.groupby("product"):
    line = f"{product:<15}"
    for row in rows.itertuples():
        cell = f"{row.rate:>7.1%} of {row.n:>5,}"
        line += f"{cell:>16}"
    print(line)

# Each exposure's TTC PD, whether a floor lifts it, and its PIT PD.
b = capital.book(con)
b["pd"] = capital.ttc_pd(con, b, pools)
b["floored"] = capital.floor_pd(b["pd"], b.cls) > b["pd"]
pit = capital.provisions().set_index("account_id")["pd12"]
b["pit"] = b.account_id.map(pit)
ok = b[~b.in_default & (b.drawn_cents > 0)]
print("\nperforming exposures, PD weighted by balance")
print(f"{'product':<20}{'TTC':>7}{'PIT':>7}{'at floor':>10}")
for product, g in ok.groupby("product"):
    ttc_avg = weighted(g["pd"], g.drawn_cents)
    pit_avg = weighted(g.pit, g.drawn_cents)
    print(f"{product:<20}{ttc_avg:>7.2%}{pit_avg:>7.2%}"
          f"{g.floored.sum():>10,}")
ttc_avg = weighted(ok["pd"], ok.drawn_cents)
pit_avg = weighted(ok.pit, ok.drawn_cents)
print(f"{'all':<20}{ttc_avg:>7.2%}{pit_avg:>7.2%}"
      f"{ok.floored.sum():>10,}")
print("PIT: Chapter 20's 12-month PD, weighted across its scenarios")
