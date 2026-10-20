# The appetite and the pack, read back: what is saved, and the pack
# written again from the saved files to prove it is what they give.
from ballast import appetite as ap
from ballast import report
from ballast.config import ROOT

for d in ("appetite", "report"):
    for f in sorted((ROOT / "data" / "ballast" / d).iterdir()):
        size = f.stat().st_size / 1024
        print(f"  {d + '/' + f.name:<36}{size:>6.1f} KB")
a = ap.load()
print(f"statement: {len(a['statement'])} metrics, as at {a['as_of']}, "
      f"for {a['meeting']}")
print(f"plan: {len(a['plan']['steps'])} steps; watchlist limit "
      f"${a['watchlist']['appetite'] / 1e8:,.1f}m")
saved = (ROOT / "data" / "ballast" / "report" / "pack_2026-01.md"
         ).read_text()
again = report.pack()
same = "identical" if again == saved else "DIFFERS"
print(f"pack written again: {same}, {len(again.splitlines())} lines")
print(f"decisions requested: {len(report.decisions(a))}")
