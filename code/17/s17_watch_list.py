# Exercise 17.4: a market watch list. Flag a listed client in any
# month its DD is below 1.5 while its internal grade is 6 or better.
import fernhill
from _listed import listed_panel, next_year

con = fernhill.connect()
s = next_year(listed_panel(con))
s = s[s.internal_grade.notna()]
f = s[(s.dd < 1.5) & (s.internal_grade <= 6)]
print(f"months flagged: {len(f)} of {len(s):,}, on "
      f"{f.company_id.nunique()} companies")
print(f"  followed by a default within a year: {f.y.sum()} "
      f"({f.y.mean():.0%}); all months {s.y.mean():.1%}")
later = f.groupby("company_id").default_month.first().notna()
print(f"  flagged companies that defaulted at some point: "
      f"{later.sum()} of {len(later)}")
d = s[s.default_month.notna()]
grades = d[d.dd < 1.5].groupby("company_id").internal_grade.min()
print(f"defaulters whose DD fell below 1.5: {len(grades)}; their best"
      f" grade\n  in those months: "
      + ", ".join(f"{g:.0f}" for g in sorted(grades)))
