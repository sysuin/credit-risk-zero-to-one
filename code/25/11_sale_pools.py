# Fernhill's two debt sales: which charged-off debts went, which were
# kept, and whether the kept ones are a fair comparison for the sold.
import fernhill
from ballast import collections as coll


def describe(g):
    """Each row of the comparison, worked out for one group of debts."""
    off = g["off_cents"].sum()
    owed = g["owed_cents"].sum()
    price = g["price_cents"].sum()
    later = g["after_net"].sum()
    return {
        "debts": f"{len(g):,}",
        "months since charge-off": f"{g['age_months'].mean():.1f}",
        "written off, average $": f"{g['off_cents'].mean() / 100:,.0f}",
        "cards": f"{g['product'].eq('card').mean():.0%}",
        "collected before, cents":
            f"{100 * g['before_gross'].sum() / off:.1f}",
        "paid in last 6 months": f"{g['last6_gross'].gt(0).mean():.0%}",
        "still owed, $": f"{owed / 100:,.0f}",
        "price, $": f"{price / 100:,.0f}",
        "later collections, net $": f"{later / 100:,.0f}",
        "cents per $ still owed": f"{100 * (price + later) / owed:.2f}",
    }


con = fernhill.connect()
for sale, price in coll.SALES.items():
    wide = coll.sale_pool(con, sale, min_age=6, max_age=120)
    sold = wide[wide["sold"]]
    oldest = int(sold["age_months"].max())
    print(f"{sale:%b %Y} at {price * 100:.0f} cents: the debts sold "
          f"were charged off")
    print(f"  6 to {oldest} months before")
    # Debts kept that were older than anything the buyer took.
    older = wide[~wide["sold"] & (wide["age_months"] > oldest)]
    if len(older) >= 10:
        owed = older["owed_cents"].sum()
        cents = 100 * older["after_net"].sum() / owed
        word = "debt" if len(older) == 1 else "debts"
        print(f"  kept and older than that: {len(older):,} {word}, "
              f"${older['owed_cents'].sum() / 100:,.0f} owed,")
        print(f"  which later brought in {cents:.2f} cents a dollar")
    # The fair comparison: sold and kept debts of the same ages.
    pool = wide[wide["age_months"] <= oldest]
    print(f"  {'':<26}{'sold':>12}{'kept':>12}")
    sold_rows = describe(pool[pool["sold"]])
    kept_rows = describe(pool[~pool["sold"]])
    for name in sold_rows:
        print(f"  {name:<26}{sold_rows[name]:>12}{kept_rows[name]:>12}")
    print(f"  kept share of the pool: {(~pool['sold']).mean():.1%}\n")
print("later collections run to December 2025; cents per $ is the")
print("price for sold debts, later net collections for kept ones")
