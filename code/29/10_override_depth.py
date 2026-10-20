# How far below the cut-off branch managers overrode, and how the loans
# they approved went in their first year, beside the score's own.
import fernhill
from ballast import governance as gv

con = fernhill.connect()
a = gv.scored_applications(con)
bad = gv.first_year_bad(con)
low = a[a["override"] == "low_side"].copy()
low["depth"] = gv.depth_band(low["margin"])
print(f"{len(low)} low-side overrides: median "
      f"{-low.margin.median():.0f} points below, "
      f"deepest {-low.margin.min():.0f}")

booked = a[a.outcome == "booked"].merge(bad, on="account_id")
booked["group"] = booked["zone"].map(
    {"below": "", "band": "refer band, decided",
     "above": "above the band"})
ov = booked["override"] == "low_side"
booked.loc[ov, "group"] = "override, " + gv.depth_band(
    booked.loc[ov, "margin"])
print("\nbooked loans opened by 2024, bad in the first 12 months")
print(f"{'':<32}{'applied':>8}{'loans':>7}{'bad':>6}{'bad rate':>10}")
order = [f"override, {n}" for _, n in gv.DEPTH_BANDS] + \
    ["refer band, decided", "above the band"]
for gname in order:
    g = booked[booked.group == gname]
    n_app = (low.depth == gname.split(", ")[1]).sum() \
        if gname.startswith("override") else ""
    print(f"{gname:<32}{n_app:>8}{len(g):>7,}{int(g.bad.sum()):>6,}"
          f"{g.bad.mean():>10.1%}")
