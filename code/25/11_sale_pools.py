# Fernhill's two debt sales: which charged-off debts went, which were
# kept, and whether the kept ones are a fair comparison for the sold.
import fernhill
from ballast import collections as coll

con = fernhill.connect()
for sale, price in coll.SALES.items():
    wide = coll.sale_pool(con, sale, min_age=6, max_age=120)
    sold = wide[wide["sold"]]
    oldest = int(sold["age_months"].max())
    print(f"{sale:%b %Y} at {price * 100:.0f} cents: the debts sold "
          f"were charged off")
    print(f"  6 to {oldest} months before")
    older = wide[~wide["sold"] & (wide["age_months"] > oldest)]
    if len(older) >= 10:
        owed = older["owed_cents"].sum()
        cents = 100 * older["after_net"].sum() / owed
        word = "debt" if len(older) == 1 else "debts"
        print(f"  kept and older than that: {len(older):,} {word}, "
              f"${older['owed_cents'].sum() / 100:,.0f} owed,")
        print(f"  which later brought in {cents:.2f} cents a dollar")
    pool = wide[wide["age_months"] <= oldest]
    print(f"  {'':<26}{'sold':>12}{'kept':>12}")
    stats = {
        "debts": lambda g: f"{len(g):,}",
        "months since charge-off": lambda g:
            f"{g['age_months'].mean():.1f}",
        "written off, average $": lambda g:
            f"{g['off_cents'].mean() / 100:,.0f}",
        "cards": lambda g: f"{g['product'].eq('card').mean():.0%}",
        "collected before, cents": lambda g:
            f"{100 * g['before_gross'].sum()
               / g['off_cents'].sum():.1f}",
        "paid in last 6 months": lambda g:
            f"{g['last6_gross'].gt(0).mean():.0%}",
        "still owed, $": lambda g:
            f"{g['owed_cents'].sum() / 100:,.0f}",
        "price, $": lambda g: f"{g['price_cents'].sum() / 100:,.0f}",
        "later collections, net $": lambda g:
            f"{g['after_net'].sum() / 100:,.0f}",
        "cents per $ still owed": lambda g: f"{100 * (
            g['price_cents'].sum() + g['after_net'].sum())
            / g['owed_cents'].sum():.2f}",
    }
    for name, f in stats.items():
        print(f"  {name:<26}{f(pool[pool['sold']]):>12}"
              f"{f(pool[~pool['sold']]):>12}")
    print(f"  kept share of the pool: {(~pool['sold']).mean():.1%}\n")
print("later collections run to December 2025; cents per $ is the")
print("price for sold debts, later net collections for kept ones")
