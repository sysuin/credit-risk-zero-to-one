# Who approves each commercial client at its annual review, on the
# analysts' grade and on the model's: where a grade moves the decision.
import fernhill
from ballast import governance as gv
from ballast.config import AS_OF

con = fernhill.connect()
rank = {lv: i for i, lv in enumerate(gv.LEVELS)}


def routed(month):
    c = gv.client_exposures(con, month)
    c["by_grade"] = [gv.approver(e, g)
                     for e, g in zip(c.exposure_cents, c.grade)]
    c["by_model"] = [gv.approver(e, g)
                     for e, g in zip(c.exposure_cents, c.model_grade)]
    return c


march = AS_OF.replace(month=3, day=31)
c = routed(march)
print(f"{len(c)} clients at the {march:%B %Y} review: who approves")
print(f"{'':<24}{'clients':>8}{'$m':>8}{'on model grade':>16}")
for lv in gv.LEVELS:
    s = c[c.by_grade == lv]
    print(f"{lv:<24}{len(s):>8}{s.exposure_cents.sum() / 1e8:>8,.0f}"
          f"{(c.by_model == lv).sum():>16}")

print("\nreviews where the analysts' grade changes the approver")
print(f"{'review':<8}{'clients':>8}{'sent higher':>13}"
      f"{'sent lower':>12}")
tot = [0, 0]
for y in range(2018, AS_OF.year + 1):
    c = routed(march.replace(year=y))
    a = c.by_grade.map(rank)
    m = c.by_model.map(rank)
    hi, lo = int((a > m).sum()), int((a < m).sum())
    tot = [tot[0] + hi, tot[1] + lo]
    print(f"{y:<8}{len(c):>8}{hi:>13}{lo:>12}")
print(f"{'all':<8}{'':>8}{tot[0]:>13}{tot[1]:>12}")
