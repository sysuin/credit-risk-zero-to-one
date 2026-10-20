# Who the sample can see: outcomes exist only where Fernhill lent.
import fernhill
from ballast.scorecard import sample

con = fernhill.connect()
out = sample.outcomes(con)[["app_id", "outcome", "bad"]]
apps = con.execute("""
    SELECT app_id, mark1_score - cutoff AS margin, outcome AS result,
           worst_status_24m, public_records, bureau_hit, age
    FROM applications
    WHERE product = 'personal' AND app_date BETWEEN ? AND ?
""", [sample.DEV_FROM, sample.DEV_TO]).df()
d = apps.merge(out, on="app_id", how="left")
d["band"] = d["margin"].apply(
    lambda m: "1 below refer" if m < -10 else "2 refer band"
    if m < 10 else "3 10-39 above" if m < 40 else "4 40+ above")

print("development applications by Mark I points from the cut-off")
print(f"{'band':<16}{'applied':>9}{'booked':>8}{'share':>7}"
      f"{'bads':>6}{'bad rate':>10}")
for band, g in d.groupby("band"):
    booked = g["result"] == "booked"
    known = g[booked & (g["outcome"] != "indeterminate")]
    rate = f"{known['bad'].mean():.1%}" if len(known) else "-"
    print(f"{band[2:]:<16}{len(g):>9,}{int(booked.sum()):>8,}"
          f"{booked.mean():>7.1%}{int(known['bad'].sum()):>6,}"
          f"{rate:>10}")

booked = d[d["result"] == "booked"]
print()
print(f"{'':<34}{'applied':>9}{'booked':>8}")
for label, test in [
        ("worst status 90+ in two years", d["worst_status_24m"] >= 90),
        ("a public record", d["public_records"] > 0),
        ("no file and under 25", ~d["bureau_hit"] & (d["age"] < 25))]:
    print(f"{label:<34}{int(test.sum()):>9,}"
          f"{int(test[booked.index].sum()):>8,}")
