# What Fernhill holds about protected characteristics, which code reads
# it, and which of its scorecards use age.
import textwrap

import fernhill
from ballast.config import ROOT
from ballast.decision import engine
from ballast.decision import policy as pol

con = fernhill.connect()
n_apps, n_mon, joined = con.execute("""
    SELECT (SELECT count(*) FROM applications),
           (SELECT count(*) FROM applicant_monitoring),
           (SELECT count(*) FROM applications
            JOIN applicant_monitoring USING (app_id))""").fetchone()
print(f"applications {n_apps:,}; monitoring rows {n_mon:,}; "
      f"matched {joined:,}")
for g, n in con.execute("""SELECT gender, count(*) FROM
        applicant_monitoring GROUP BY 1 ORDER BY 2 DESC""").fetchall():
    print(f"  {g}  {n:>7,}  {n / n_mon:6.1%}")

code = ROOT / "code" / "ballast"
readers = sorted(str(p.relative_to(code)) for p in code.rglob("*.py")
                 if "applicant_monitoring" in p.read_text())
print(f"\nBallast modules that read the monitoring table: {readers}")

edges, pts = pol.MARK1["age"]
bands = ["under 25", "25-34", "35-49", "50 and over"]
print("\nMark I's age line: " + ", ".join(
    f"{b} {p}" for b, p in zip(bands, pts)))
card = engine.load_champion(pol.load_policy())
print(textwrap.fill("Mark II-R's lines: " + ", ".join(
    card.characteristics), width=66, subsequent_indent="  "))
