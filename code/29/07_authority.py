# Fernhill's lending authority for commercial credit, and Meridian's
# revolver put through it at the model's grade and at the one assigned.
import sys

import fernhill
from ballast import governance as gv
from ballast.config import AS_OF, ROOT

sys.path.append(str(ROOT / "code" / "15"))
import _meridian  # noqa: E402  Chapter 15's helper: Meridian's case

con = fernhill.connect()
m = gv.authority_matrix()
print("Most one level may approve, total exposure to a client ($m)")
print(f"{'grade':<7}{'PD':>7}{'senior officer':>16}"
      f"{'chief officer':>15}{'committee':>11}")
for g in m.columns:
    cells = [f"{v / 1e8:.1f}" if v else "-" for v in m[g]]
    print(f"{g:<7}{gv.MASTER_SCALE[g]:>7.2%}{cells[0]:>16}"
          f"{cells[1]:>15}{cells[2]:>11}")
cet1 = con.execute("SELECT cet1_cents FROM bank_capital "
                   "WHERE year_end = ?", [AS_OF]).fetchone()[0]
print(f"above every level: the {gv.BOARD}; committee cap "
      f"${gv.AUTHORITY[-1][2] / 1e8:.0f}m\n  against a tenth of CET1 "
      f"(${cet1 / 1e8:,.0f}m): ${cet1 / 1e9:,.1f}m")

a = _meridian.analysis(con)
asked = a["request"][0]
print(f"\nMeridian Supply Co.: asked for ${asked / 1e8:.1f}m, "
      f"recommended ${a['limit'] / 1e8:.1f}m")
for label, g in (("model's grade", 3), ("assigned grade", 5)):
    print(f"  at the {label} {g}: {gv.approver(a['limit'], g)}")
