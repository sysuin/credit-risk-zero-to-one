# Ballast v0.5 prices every personal loan it approves in 2025 on the
# 2026 grid, set beside the prices Fernhill quoted the same people.
import sys

import fernhill
from ballast import data, pricing
from ballast.config import ROOT
from ballast.decision import engine
from ballast.decision import policy as pol

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, market, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
m = market(con)
costs = pricing.Costs(lgd=lgd)
life = round(pricing.value(1_200_000, 12.0, 36, float(fd.annual(585)),
                           float(fp.annual(585)), m, costs).life_months)
grid = pricing.Grid(edges=(565, 580, 595, 610),
                    rates=(17.65, 15.00, 12.65, 11.40, 10.75),
                    at_ftp_pct=round(pricing.ftp_pct(m, life), 2),
                    life_months=life)
p = pricing.Pricing(grid, fd, fp, costs, m,
                    {"market": "2025-12-31", "fits": "loans applied "
                     "for 2019-2023", "lgd": "defaults 2016-2022"})
path = pricing.save_pricing(p)
assert pricing.load_pricing() == p
print(f"Saved {path.relative_to(path.parents[2])}: set at a transfer"
      f" price of {grid.at_ftp_pct:.2f}%\n  ({life}-month life), "
      "moving point for point with it")
for name, r in zip(grid.labels(550, 652), grid.rates):
    print(f"  Mark II-R {name:<8} {r:>6.2f}%")

raw = data.load_applications(con, unknowns=False)
apps = raw[raw["product"].astype(str).eq("personal")
           & (raw["app_date"].astype(str) >= "2025-01-01")]
policy = pol.load_policy()
d = engine.decide_all(apps, policy, engine.load_champion(policy))
yes = d[d["decision"].isin(["approve", "refer"])].copy()
yes["rate"] = grid.rate(yes["score"])
yes["fern"] = apps.loc[yes.index, "offered_rate_pct"].astype(float)
yes["arm"] = apps.loc[yes.index, "price_test_arm"].astype(object)
both = yes[yes["fern"].notna() & yes["arm"].isna()]
diff = both["rate"] - both["fern"]
print(f"\nBallast approves or refers {len(yes):,} applications")
print(f"Of these, Fernhill quoted {len(both):,}: on average "
      f"{both['fern'].mean():.2f}%;\n  Ballast "
      f"{both['rate'].mean():.2f}%")
print(f"  a point or more cheaper {(diff <= -1).mean():.1%}, within "
      f"a point {(diff.abs() < 1).mean():.1%},\n  a point or more "
      f"dearer {(diff >= 1).mean():.1%}")
big = both.loc[diff.abs() >= 3]
print(f"  three points or more apart: {len(big):,}; of them Ballast "
      f"dearer {int((diff[big.index] > 0).sum())}")

one = a[a["app_id"].eq("A00072101")].iloc[0]
amt = int(one["offered_amount_cents"])
term = int(one["term_requested_months"])
q = pricing.price_application(p, int(one["m2r"]), amt, term)
old = pricing.value(amt, one["offered_rate_pct"], term, q["annual_pd"],
                    q["annual_prepay"], m, costs)
print(f"\n{one['app_id']} ({one['channel']}): Mark I "
      f"{one['mark1_score']}, Mark II-R {one['m2r']},\n  "
      f"${amt / 100:,.0f} over {term} months")
print(f"  Fernhill quoted {one['offered_rate_pct']:.2f}% and the "
      f"applicant walked away")
print(f"  Ballast: tier {q['tier']} at {q['rate']:.2f}%; floor "
      f"{q['floor']:.2f}%; RAROC {q['raroc']:.0%}")
print(f"  default {q['annual_pd']:.1%} a year, prepay "
      f"{q['annual_prepay']:.0%}; at {one['offered_rate_pct']:.2f}% "
      f"the RAROC is {old.raroc:.0%}")
