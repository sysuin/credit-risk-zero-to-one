#!/usr/bin/env python3
"""
Check that everything the book needs is in place, before you spend an afternoon
discovering it is not.

    python3 code/_preflight.py

Nothing here needs a network connection, and the book uses no secrets.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

CHECKS: list[tuple[str, bool, str]] = []

# What each part of the book first needs. Import name, and the part that needs it.
PACKAGES = [
    ("numpy", "Part I"), ("pandas", "Part I"), ("duckdb", "Part I"), ("pyarrow", "Part I"),
    ("scipy", "Part II"), ("statsmodels", "Part II"), ("sklearn", "Part II"),
    ("lightgbm", "Part II"),
]


def check(label: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((label, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if detail else ""))
    return ok


def main() -> int:
    print("\nEnvironment")
    check("Python 3.12 or newer", sys.version_info >= (3, 12),
          ".".join(map(str, sys.version_info[:3])))
    for package, part in PACKAGES:
        try:
            module = importlib.import_module(package)
            version = getattr(module, "__version__", "")
            check(f"{package} installed", True, version)
        except ImportError:
            check(f"{package} installed", False,
                  f"needed from {part}: pip install -r requirements.txt")

    print("\nThe loan book")
    from ballast.config import LOANBOOK, ROOT, TRUTH
    for label, path in (("Fernhill's loan book present", LOANBOOK),
                        ("The truth database present", TRUTH)):
        check(label, path.exists(),
              str(path.relative_to(ROOT)) if path.exists() else "run: make data")
    free = shutil.disk_usage(ROOT).free / 1e9
    check("at least 1 GB of disk free", free >= 1.0, f"{free:.1f} GB")

    failed = [label for label, ok, _ in CHECKS if not ok]
    print(f"\n  {len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print(f"  Fix first: {failed[0]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
