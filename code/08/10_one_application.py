# Score one out-of-time applicant with Mark II, line by line.
import fernhill
from ballast.scorecard import model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)

oot = s[s["split"] == "out_of_time"].sort_values("app_id")
row = oot.iloc[0]
print(f"{row['app_id']}  applied {row['app_date']}  "
      f"outcome {row['outcome']}")
lines = card.explain(row)
for _, ln in lines.iterrows():
    v = ln["value"]
    if isinstance(v, float):
        shown = f"{v:,.0f}" if v.is_integer() else f"{v:,.2f}"
    else:
        shown = str(v)
    print(f"  {ln['characteristic']:<22}{shown:>11}  {ln['bin']:<14}"
          f"{ln['points']:>4}")
total = card.base + lines["points"].sum()
print(f"  {'base':<49}{card.base:>4}")
print(f"  {'Mark II score':<49}{total:>4}")
print(f"the scale says odds {points.odds_at(total):.0f} to 1, "
      f"a bad rate of {points.bad_rate_at(total):.1%}")

con = fernhill.connect()
m1, cut = con.execute("SELECT mark1_score, cutoff FROM applications "
                      "WHERE app_id = ?", [row["app_id"]]).fetchone()
print(f"Mark I scored the same application {m1} "
      f"against a cut-off of {cut}")
