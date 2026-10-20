# The findings log: what the book found about Ballast's and Fernhill's
# models, with severity and status, joined with what Chapter 23's
# validations found, and what is still open where.
import json
import textwrap

from ballast import governance as gv

inv = {e["id"]: e for e in gv.load_inventory()}
SEV = {"high": "high", "medium": "med", "low": "low"}
print(f"{'id':<4}{'model':<6}{'ch':<7}{'sev':<5}{'status':<10}issue")
for f in gv.FINDINGS:
    print(f"{f['id']:<4}{f['model']:<6}{f['chapters']:<7}"
          f"{SEV[f['severity']]:<5}{f['status']:<10}{f['issue']}")

same = ", ".join(f"{f['id']} = {f['same_as']}" for f in gv.FINDINGS
                 if f["same_as"])
print("\n" + textwrap.fill("also found by Chapter 23's validations: "
                           + same, 68))
new = gv.new_from_validation()
ids = ", ".join(f"{f['id']} {SEV[f['severity']]}"
                + (" (blocks use)" if f["blocks"] else "") for f in new)
head = f"new in those validations ({len(new)}): "
print(textwrap.fill(head + ids, 68))

log = gv.FINDINGS + new
t = gv.findings_table(log)
print(f"\n{'':<9}" + "".join(f"{s:>10}" for s in t.columns))
for sev, row in t.iterrows():
    print(f"{sev:<9}" + "".join(f"{n:>10}" for n in row))
open_high = sorted({f["model"] for f in log
                    if f["severity"] == "high" and f["status"] == "open"
                    and inv[f["model"]]["status"] in gv.IN_USE})
print("in use with an open high finding: " + ", ".join(open_high))
(gv.OUT / "findings.json").write_text(
    json.dumps(log, indent=1) + "\n")
