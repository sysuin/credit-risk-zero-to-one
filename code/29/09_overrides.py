# Retail overrides measured: low-side approvals below Mark I's refer
# band and high-side declines above it, by year and by region.
import fernhill
from ballast import governance as gv

con = fernhill.connect()
a = gv.scored_applications(con)
a["year"] = a["app_date"].dt.year
low = a["override"] == "low_side"
high = a["override"] == "high_side"
below, above = a["zone"] == "below", a["zone"] == "above"
branch = a["channel"] == "branch"

print(f"{'year':<6}{'below band':>11}{'low-side':>9}{'rate':>7}"
      f"{'branch rate':>12}{'high-side':>11}{'rate':>7}")
for y, g in a.groupby("year"):
    b, br = g.zone == "below", (g.zone == "below") & (g.channel ==
                                                        "branch")
    lo = (g.override == "low_side") & b
    hi = (g.override == "high_side") & (g.zone == "above")
    print(f"{y:<6}{b.sum():>11,}{lo.sum():>9}{lo.sum() / b.sum():>7.2%}"
          f"{(lo & br).sum() / br.sum():>12.2%}{hi.sum():>11}"
          f"{hi.sum() / (g.zone == 'above').sum():>7.2%}")
print(f"low-side outside branches: {(low & ~branch).sum()}; "
      f"recorded inside the refer band: {(low & ~below).sum()}")

bb = below & branch
p = (low & bb).sum() / bb.sum()
print(f"\nbranch low-side rate by region, 2016-2025 "
      f"(bank {p:.2%})")
print(f"{'region':<13}{'below band':>11}{'overrides':>10}{'rate':>7}"
      f"{'z':>7}")
for r, g in a[bb].groupby("region"):
    x = int((g.override == "low_side").sum())
    print(f"{r:<13}{len(g):>11,}{x:>10}{x / len(g):>7.2%}"
          f"{gv.binomial_z(x, len(g), p):>+7.1f}")
