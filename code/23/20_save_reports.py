# Every validation in one table, saved where the model inventory can
# read it, and read back.
from ballast import validation as vd
from ballast.config import AS_OF, ROOT

reports = list(vd.REPORTS.values())
d = vd.VALIDATION_DATE
print(f"Validations dated {d.day} {d:%B %Y}, data to "
      f"{AS_OF.day} {AS_OF:%B %Y}")
print("\n".join(vd.summary_lines(reports)))
files = vd.save(reports)
print(f"\nSaved {len(files)} files to "
      f"{files[0].parent.relative_to(ROOT)}/:")
names = [f.name for f in files]
print("  " + ", ".join(names[:4]) + ",\n  " + ", ".join(names[4:]))
print(f"\nWhat the register reads back\n  {'id':<6}{'year':<6}"
      f"{'conclusion':<26}high/med/low")
for k, e in vd.register_entries().items():
    print(f"  {k:<6}{e['validated']:<6}{e['conclusion']:<26}"
          f"{e['high']}/{e['medium']}/{e['low']}")
