# Ballast v0.8's capital run as saved for later chapters: RWA by
# account, checked by running the IRB formula again from the saved
# inputs, and the summary by product.
import pandas as pd
from ballast import capital
from ballast.config import AS_OF

r = capital.load()
again = capital.irb(r.drop(columns=["irb_rwa", "el", "k"]))
print(f"rwa_{AS_OF}.parquet: {len(r):,} exposures, "
      f"{r.shape[1]} columns")
print(f"IRB RWA saved ${r.irb_rwa.sum() / 100:,.0f}; "
      f"run again ${again.irb_rwa.sum() / 100:,.0f}")
p = pd.read_csv(capital.OUT / f"rwa_by_product_{AS_OF}.csv",
                index_col=0)
print(f"\n{'$m':<20}{'SA RWA':>9}{'IRB RWA':>9}{'IRB EL':>8}")
for k, x in p.iterrows():
    print(f"{k:<20}{x.sa_rwa / 1e6:>9,.1f}{x.irb_rwa / 1e6:>9,.1f}"
          f"{x.el / 1e6:>8,.2f}")
s = r.groupby("segment")[["sa_rwa", "irb_rwa"]].sum() / 1e8
for k, x in s.iterrows():
    print(f"{k:<20}{x.sa_rwa:>9,.1f}{x.irb_rwa:>9,.1f}")
