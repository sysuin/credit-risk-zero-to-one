# Implemented as documented? Rebuild Mark II's sample from the loan
# book and compare it with the saved one; rescore 2025's applications
# from the saved points table and compare with the engine's decisions.
import pandas as pd

import fernhill
from ballast import data
from ballast.config import BALLAST
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import sample

con = fernhill.connect()
saved = sample.load_sample()
built = sample.build_sample(con)
saved.attrs, built.attrs = {}, {}
same = saved.merge(built, on="app_id", suffixes=("", "_new"))
print(f"Sample: saved {len(saved):,} loans, rebuilt {len(built):,}, "
      f"matched {len(same):,}")
split = (same["split"] == same["split_new"]).mean()
outcome = (same["outcome"] == same["outcome_new"]).mean()
print(f"  same split {split:.1%}, same outcome {outcome:.1%}")
t = saved.groupby(["split", "outcome"]).size().unstack()
print(f"  {'':<13}" + "".join(f"{c:>15}" for c in t.columns))
for split, r in t.iterrows():
    print(f"  {split:<13}" + "".join(f"{v:>15,}" for v in r))

p = pol.load_policy()
card = engine.load_champion(p)
lines = card.table.groupby("characteristic", sort=False)["points"]
print(f"\nChampion {p.champion}: {len(card.characteristics)} lines, "
      f"base {card.base}, top score {card.base + lines.max().sum()}, "
      f"cut-off {p.cutoff}")
raw = data.load_applications(con, unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
rescored = pd.Series(card.score(engine.prepare(apps)).to_numpy(),
                     index=apps["app_id"].astype(str).to_numpy())
dec = pd.read_parquet(BALLAST / "decision" / "decisions_2025.parquet")
dec = dec[dec["stage"] == "score"].set_index("app_id")
gap = (rescored[dec.index] - dec["score"]).abs()
print(f"2025 applications scored by the engine: {len(dec):,}; "
      f"rescored\nfrom the saved table: {len(gap):,}, identical "
      f"{(gap == 0).sum():,}, largest gap {gap.max()}")
