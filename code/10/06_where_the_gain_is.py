# Where the challenger's gain comes from: fields, shapes, or fraud?
import fernhill
from ballast.models import gbm
from ballast.scorecard import metrics, model, points, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"].copy()
det["mark2"] = points.load_scorecard().score(det)
eight = [c for c in model.CHARACTERISTICS if c != "bureau_file"]
alone = [[i] for i in range(len(gbm.FEATURES))]
fits = {
    "challenger, 21 characteristics": gbm.fit(s),
    "Mark II's 8, raw": gbm.fit(s, features=eight),
    "21, no interactions": gbm.fit(
        s, params={"interaction_constraints": alone}),
}
for name, m in fits.items():
    det[name] = m.score(det)

# Bads that never made their first payment: a pattern Chapter 13
# reads as a warning of fraud.
con = fernhill.connect()
first = con.execute("""
    SELECT a.app_id FROM applications a
    JOIN accounts c ON c.account_id = a.account_id
    JOIN performance p ON p.account_id = c.account_id
    WHERE a.product = 'personal' AND p.missed > 0
      AND datediff('month', c.open_date, p.month) = 1
    ORDER BY a.app_id""").df()["app_id"]
det["first_missed"] = det["app_id"].isin(first) & (det["bad"] == 1)
print("bads missing the first payment: " + ", ".join(
    f"{k} {g['first_missed'].sum()}/{g['bad'].sum()}"
    for k, g in det.groupby("split", sort=False)
    if k != "train"))


def row(label, d, col):
    g = [metrics.gini(d.loc[d["split"] == k, col],
                      d.loc[d["split"] == k, "bad"])
         for k in ("holdout", "out_of_time")]
    m2 = [metrics.gini(d.loc[d["split"] == k, "mark2"],
                       d.loc[d["split"] == k, "bad"])
          for k in ("holdout", "out_of_time")]
    print(f"{label:<31}{g[0]:>6.3f}{g[0] - m2[0]:>+7.3f}"
          f"{g[1]:>7.3f}{g[1] - m2[1]:>+7.3f}")


print()
print(f"{'':<31}{'holdout':>13}{'out of time':>14}")
print(f"{'model':<31}{'Gini':>6}{'gain':>7}{'Gini':>7}{'gain':>7}")
row("Mark II", det, "mark2")
for name, m in fits.items():
    row(name, det, name)
print("without the first-payment bads:")
rest = det[~det["first_missed"]]
row("  Mark II", rest, "mark2")
row("  challenger", rest, "challenger, 21 characteristics")
