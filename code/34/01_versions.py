# The exact versions behind this book's printed output, and its floors.
import platform
import re
from importlib.metadata import PackageNotFoundError, version

import duckdb

from ballast.config import ROOT

# A line of requirements.txt that names a package: name>=floor.
REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)>=([\d.]+)")
TOOLCHAIN = "# --- The toolchain"     # the heading of the last group
PRINTED = {"matplotlib", "pytest"}    # toolchain that shapes output

rows, tools = [], []
group = rows
for line in (ROOT / "requirements.txt").read_text().splitlines():
    if line.startswith(TOOLCHAIN):
        group = tools
    m = REQUIREMENT.match(line.strip())
    if m:
        name, floor = m.groups()
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = "not installed"
        target = rows if name in PRINTED else group
        target.append((name, floor, installed))

print(f"Python {platform.python_version()}"
      f" ({platform.python_implementation()}),"
      f" {platform.platform(terse=True)} on {platform.machine()}\n")
print(f"{'package':<18}{'at least':>10}{'this book ran':>16}")
for name, floor, installed in rows:
    print(f"{name:<18}{floor:>10}{installed:>16}")
print("\nThe rest of the repository's toolchain:")
for i in range(0, len(tools), 3):
    print("  " + "   ".join(f"{n} {v}" for n, _, v in tools[i:i + 3]))

engine, source = duckdb.execute(
    "SELECT library_version, source_id FROM pragma_version()"
).fetchone()
print(f"\nDuckDB's engine: {engine}, build {source}")
