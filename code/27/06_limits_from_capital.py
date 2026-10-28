# Limits from capital: each segment's budget of economic capital,
# divided by the capital a dollar of its exposure uses.
import fernhill
from ballast import appetite as ap

con = fernhill.connect()
cap = ap.capital_now(con)
tgt = ap.capital_target(cap, ap.stress.load()["summary"])["target"]
m = 1e8
room = cap["cet1"] / tgt - cap["sa_rwa"]
print(f"regulatory: CET1 / {tgt:.1%} carries RWA of "
      f"${cap['cet1'] / tgt / m:,.0f}m, against "
      f"${cap['sa_rwa'] / m:,.0f}m")
print(f"  today: room for ${room / m:,.0f}m more")
print(f"  at the retail weight of 75%, ${room / 0.75 / m:,.0f}m of "
      "retail lending")
budget = ap.ec_ceiling(cap) * cap["cet1"]
print(f"economic: budget ${budget / m:,.1f}m against "
      f"${ap.pf.load()['ec_999'] / m:,.1f}m used")

t = ap.returns(con)
c = ap.allocate(ap.pf.load_contributions(), ap.pf.load()["ec_999"])
f = ap.segment_frame(ap.ecl.load(), ap.capital.load(), c)["c"]
# Every retail pool counts as "retail"; clients keep their grade band.
seg = f.seg.where(f.kind == "name", "retail")
ead = f.groupby(seg).ead.sum()
ec = f.groupby(seg).ec.sum()
# Fernhill's allocation: retail and grades 1-5 may grow by a quarter,
# grades 6-8 keep what they use, the watchlist gets what is left.
alloc = {"retail": 1.25 * ec["retail"],
         "grades 1-5": 1.25 * ec["grades 1-5"],
         "grades 6-8": ec["grades 6-8"]}
alloc["grades 9-10"] = budget - sum(alloc.values())
print(f"\n{'segment':<13}{'EAD':>8}{'EC':>7}{'per $':>7}{'budget':>8}"
      f"{'EAD limit':>11}{'change':>9}")
for k in ("retail", "grades 1-5", "grades 6-8", "grades 9-10"):
    d = ec[k] / ead[k]
    lim = alloc[k] / d
    print(f"{k:<13}{ead[k] / m:>8,.0f}{ec[k] / m:>7.1f}{d:>7.1%}"
          f"{alloc[k] / m:>8.1f}{lim / m:>11,.0f}"
          f"{(lim - ead[k]) / m:>+9,.0f}")
print("$m; per $ = economic capital per dollar of EAD (its share of")
print("the tail); a limit is the budget divided by it")
