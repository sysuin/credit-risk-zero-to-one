# Ballast v1.0 end to end: every step rerun from the loan book or read
# as saved, each figure set beside the one its chapter printed.
# timeout: 1800
from ballast import run

report = run.run()
print("\n".join(report.summary()))
print()
print("\n".join(report.table()))
print(f"\nsaved {run.save(report).relative_to(run.ROOT)}")
