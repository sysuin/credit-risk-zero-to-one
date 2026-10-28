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
for year in sorted(a["year"].unique()):
    # count each kind of application in this year
    in_year = a["year"] == year
    n_below = (in_year & below).sum()
    n_low = (in_year & below & low).sum()
    n_branch = (in_year & below & branch).sum()
    n_low_branch = (in_year & below & branch & low).sum()
    n_above = (in_year & above).sum()
    n_high = (in_year & above & high).sum()
    print(f"{year:<6}{n_below:>11,}{n_low:>9}{n_low / n_below:>7.2%}"
          f"{n_low_branch / n_branch:>12.2%}{n_high:>11}"
          f"{n_high / n_above:>7.2%}")
print(f"low-side outside branches: {(low & ~branch).sum()}; "
      f"recorded inside the refer band: {(low & ~below).sum()}")

# each region's branch override rate against the bank's
branch_below = below & branch
bank_rate = (low & branch_below).sum() / branch_below.sum()
print(f"\nbranch low-side rate by region, 2016-2025 "
      f"(bank {bank_rate:.2%})")
print(f"{'region':<13}{'below band':>11}{'overrides':>10}{'rate':>7}"
      f"{'z':>7}")
for region, g in a[branch_below].groupby("region"):
    n = len(g)
    overrides = int((g.override == "low_side").sum())
    z = gv.binomial_z(overrides, n, bank_rate)
    print(f"{region:<13}{n:>11,}{overrides:>10}{overrides / n:>7.2%}"
          f"{z:>+7.1f}")
