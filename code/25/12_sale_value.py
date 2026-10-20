# Was selling right? The price against what the kept debts brought in,
# discounted to the sale date, with the 2023 tail projected.
import json

import pandas as pd

import fernhill
from ballast import collections as coll
from ballast.config import AS_OF, ROOT

con = fernhill.connect()
curves = {}
for sale, price in coll.SALES.items():
    wide = coll.sale_pool(con, sale, min_age=6, max_age=120)
    oldest = wide.loc[wide["sold"], "age_months"].max()
    pool = wide[wide["age_months"] <= oldest]      # as listing 11
    sold, kept = pool[pool["sold"]], pool[~pool["sold"]]
    cof = con.execute("SELECT cost_of_funds_pct FROM market_rates "
                      "WHERE month = ?", [sale]).fetchone()[0]
    rate = (cof + 5) / 100      # Chapter 19's funding basis
    f = coll.later_flows(con, kept["account_id"], sale)
    m = pd.to_datetime(f["month"])
    f["t"] = (m.dt.year - sale.year) * 12 + m.dt.month - sale.month
    owed = kept["owed_cents"].sum()
    seen = f["net_cents"].sum() / owed
    pv = coll.present_value(f["net_cents"], f["t"], rate) / owed
    last = f["t"].max()
    s12 = f.loc[f["t"] > last - 12, "net_cents"].sum()
    p12 = f.loc[f["t"].between(last - 23, last - 12), "net_cents"].sum()
    r = s12 / p12
    running = m.max() == pd.Timestamp(AS_OF)       # still paying?
    tail = s12 * r / (1 - r) / owed if running else 0.0
    tail_pv = tail / (1 + rate) ** ((last + 12) / 12)
    keep = pv + tail_pv
    gain = (price - keep) * sold["owed_cents"].sum() / 100
    print(f"{sale:%b %Y}: {len(sold):,} sold, {len(kept):,} kept, "
          f"discounted at {100 * rate:.2f}%")
    print(f"  kept debts, cents per dollar owed: seen "
          f"{100 * seen:.2f}, discounted {100 * pv:.2f}")
    if tail:
        print(f"  still to come (each year {r:.0%} of the last): "
              f"{100 * tail:.2f}, discounted {100 * tail_pv:.2f}")
    print(f"  keeping was worth {100 * keep:.2f} cents; the buyer paid "
          f"{100 * price:.0f}")
    print(f"  selling gained ${gain:,.0f} on "
          f"${sold['owed_cents'].sum() / 100:,.0f} owed")
    print(f"  break-even price: {100 * keep:.1f} cents\n")
    cum = f.groupby("t")["net_cents"].sum().cumsum() / owed
    curves[f"{sale:%b %Y}"] = {"price": price, "t": cum.index.tolist(),
                               "cents": (100 * cum).round(3).tolist()}
json.dump(curves, open(ROOT / "code/25/12_sale_value.json", "w"))
print("collections are net of the agency's commission; Fernhill's")
print("own collections costs are not in the data and would favour")
print("selling further")
