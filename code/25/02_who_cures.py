# Consumer accounts that fell one payment behind, 2016-2023: who was
# up to date again three months later, one characteristic at a time.
import numpy as np
import pandas as pd

import fernhill
from ballast import collections as coll

con = fernhill.connect()
e = coll.entries(con, "2016-01-01", "2023-12-31")
print(f"{len(e):,} entries; cured within three months "
      f"{e['cured_3m'].mean():.1%},")
print(f"rolled to 90 days {e['rolled_90'].mean():.1%}")
cuts = {
    "bureau score at application": (
        pd.cut(e["bureau_v3"].where(e["no_file"].eq(0)),
               [0, 620, 660, 700, 900],
               labels=["<620", "620-659", "660-699", "700+"])),
    "months on book": pd.cut(e["months_on_book"], [0, 6, 12, 24, 999],
                             labels=["1-6", "7-12", "13-24", "25+"]),
    "balance": pd.qcut(e["balance"], 4,
                       labels=["lowest 25%", "second", "third",
                               "highest 25%"]),
    "behind in the last 12 months": np.where(
        e["repeat"].eq(1), "yes", "no"),
    "paid part of the payment": np.where(
        e["part_paid"].eq(1), "yes", "no"),
    "product": e["product"],
}
for name, col in cuts.items():
    g = e.groupby(col, observed=True)[["cured_3m", "rolled_90"]]
    t = g.agg(["mean", "size"])
    print(f"\n{name}")
    for k, r in t.iterrows():
        print(f"  {str(k):<12} cured {r[('cured_3m', 'mean')]:>6.1%}"
              f"   rolled {r[('rolled_90', 'mean')]:>6.1%}"
              f"   {int(r[('cured_3m', 'size')]):>6,}")
