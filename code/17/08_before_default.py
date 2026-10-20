# The two years before each listed client's default: distance to
# default, Fernhill's grade and the agency's letter, and where each
# signal ranked the company among all listed clients that month.
import json
from pathlib import Path

import fernhill
from _listed import listed_panel

con = fernhill.connect()
p = listed_panel(con)
by_month = p.groupby("month")
# Rank 0-1 within the month, low = riskier; ties share their rank.
p["dd_rank"] = by_month.dd.rank(pct=True)
p["grade_rank"] = (-p.internal_grade).groupby(p.month).rank(pct=True)
names = dict(con.execute("SELECT company_id, name FROM companies")
             .fetchall())
d = p[p.before.between(0, 24)]

ks = [24, 12, 6, 3, 1]
d = d.sort_values(["default_month", "company_id"])
print(f"{'':<32}{'DD, months before':<21}{'grade'}")
print(f"{'company':<25}{'default'}" + "".join(f"{k:>4}" for k in ks)
      + " " + "".join(f"{k:>3}" for k in ks))
rated = []
for cid, x in d.groupby("company_id", sort=False):
    x = x.set_index("before")
    print(f"{names[cid]:<25}{x.default_month.iloc[0]:%b %y} "
          + "".join(f"{x.dd[k]:>4.1f}" for k in ks) + " "
          + "".join(f"{x.internal_grade[k]:>3.0f}" for k in ks))
    if x.agency_rating.notna().any():
        rated.append((names[cid], [x.agency_rating[k] for k in ks]))
print(f"\n{'agency letter':<31}" + "".join(f"{k:>4}" for k in ks))
for name, letters in rated:
    print(f"{name:<31}" + "".join(f"{x:>4}" for x in letters))

held = con.execute("""
    SELECT c.name, r.rating_date, r.model_grade, r.internal_grade
    FROM ratings r JOIN companies c USING (company_id)
    JOIN corporate_defaults d USING (company_id)
    WHERE c.listed AND r.internal_grade < r.model_grade
      AND r.rating_date BETWEEN d.default_month - INTERVAL 25 MONTH
                            AND d.default_month
    ORDER BY r.rating_date""").fetchall()
print("\nreviews in those two years where the grade was set better "
      "than\nthe rating model's")
for name, day, model, grade in held:
    print(f"  {name:<25}{day:%b %Y}   model {model:>2.0f}, "
          f"grade {grade:>2.0f}")

med = d.groupby("before")[["dd_rank", "grade_rank"]].median()
print("\nmedian rank among listed clients that month (0 = riskiest)")
print(f"  {'months before':<14}" + "".join(f"{k:>6}" for k in
                                          (24, 18, 12, 9, 6, 3, 1)))
for col, label in (("dd_rank", "by DD"), ("grade_rank", "by grade")):
    print(f"  {label:<14}" + "".join(
        f"{med[col][k]:>6.0%}" for k in (24, 18, 12, 9, 6, 3, 1)))

Path("code/17/08_before_default.json").write_text(json.dumps({
    "before": [int(k) for k in med.index],
    "dd_rank": list(med.dd_rank), "grade_rank": list(med.grade_rank),
    "dd_q1": list(d.groupby("before").dd_rank.quantile(0.25)),
    "dd_q3": list(d.groupby("before").dd_rank.quantile(0.75)),
    "grade_q1": list(d.groupby("before").grade_rank.quantile(0.25)),
    "grade_q3": list(d.groupby("before").grade_rank.quantile(0.75))}))
