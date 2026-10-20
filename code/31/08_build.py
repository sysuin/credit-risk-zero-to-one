# Ballast v1.0's quick proof: the check-only run reads every saved
# result and sets it against what its chapter printed, rerunning
# nothing slow.
from ballast import run

report = run.run(rerun=False)
print("\n".join(report.summary()))
print("all reconciled" if report.ok else "SOMETHING DIFFERS")
