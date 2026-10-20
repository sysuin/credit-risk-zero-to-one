# The supervisor's agenda, item by item, with the evidence Ballast can
# produce for each today and whether it is ready, partial or a gap.
import json

import pandas as pd

import fernhill
from ballast import governance as gv
from ballast.config import AS_OF, BALLAST

con = fernhill.connect()
inv = {e["id"]: e for e in gv.load_inventory()}
live = [e for e in inv.values() if e["tier"] is not None]
tier1 = [e for e in live if e["tier"] == 1 and e["status"] in gv.IN_USE]
ok1 = [e["id"] for e in tier1 if e["conclusion"].startswith("approved")
       and e["due"] not in ("overdue", "now")]
blocked = [e["id"] for e in tier1 if e["due"] == "blocked"]
f = pd.DataFrame(gv.FINDINGS + gv.new_from_validation())
open_high = f[(f.severity == "high") & (f.status == "open")]
_, state = gv.document("MK2R", list(inv.values()))
filled = sum(v == "filled" for v in state.values())
ecl = pd.read_parquet(BALLAST / "ecl" / f"ecl_{AS_OF:%Y-%m-%d}.parquet")
w = dict(con.execute("SELECT DISTINCT scenario, weight FROM scenarios "
                     "WHERE weight > 0 ORDER BY scenario").fetchall())
held_reason = con.execute("""SELECT count(*) FROM ratings
    WHERE analyst_override AND year(rating_date) = ?""",
                          [AS_OF.year]).fetchone()[0]
pack = (BALLAST / "monitoring" / f"pack_{AS_OF:%Y-%m}.txt").read_text()
alerts = pack.split("FOR ATTENTION")[1].split("\n\n")[0].strip()
a = gv.scored_applications(con)
b = a[(a.zone == "below") & (a.channel == "branch") &
      (a.app_date.dt.year == AS_OF.year)]

evidence = {
    "1": ("ready", f"inventory.json: {len(inv)} models, "
                   f"{sum(e['tier'] == 1 for e in live)} in tier 1"),
    "2": ("gap", f"tier 1 in use: {len(tier1)}; approved by a "
                 f"validation: {len(ok1)}; "
                 f"not approved: {len(blocked)}"),
    "3": ("partial", f"findings.json: {len(f)} logged, "
                     f"{len(open_high)} high and open; no due dates"),
    "4": ("partial", f"MK2R {inv['MK2R']['conclusion']}; MK2R.md "
                     f"{filled}/{len(state)}; Mark I none"),
    "5": ("partial", f"provision ${ecl.ecl.sum() / 1e8:,.2f}m; weights "
                     + "/".join(f"{w[k]:.2f}" for k in
                                ("upside", "base", "downside",
                                 "severe"))),
    "6": ("gap", f"{held_reason} holds in {AS_OF.year}, "
                 f"flagged with no reason on file"),
    "7": ("ready", f"policy.json, pricing.json, authority matrix: "
                   f"{len(gv.AUTHORITY)} levels"),
    "8": ("ready", f"{AS_OF.year} branch low-side rate "
                   f"{(b.override == 'low_side').mean():.2%}; "
                   f"depth limit {gv.MAX_OVERRIDE_DEPTH} points"),
    "9": ("partial", "pack section 8: Ballast 2025 F/M "
                     + pack.split("Ballast 2025")[1].split()[0]
                     + ", interval below 1"),
    "10": ("ready", f"pack_{AS_OF:%Y-%m}.txt: "
                    f"{len(alerts.splitlines())} alerts for attention"),
}
md = [f"# Examination evidence, as at {AS_OF:%d %B %Y}", ""]
for no, item in gv.AGENDA:
    st, ev = evidence[no]
    print(f"{no:>2}  {item:<44}{st:>8}")
    print(f"    {ev}")
    md += [f"## {no}. {item} ({st})", "", f"- {ev}", ""]
counts = pd.Series([v[0] for v in evidence.values()]).value_counts()
print("ready {ready}, partial {partial}, gap {gap}".format(**counts))
(gv.OUT / f"exam_{AS_OF:%Y-%m}.md").write_text("\n".join(md) + "\n")
(gv.OUT / "exam.json").write_text(json.dumps(evidence, indent=1) + "\n")
