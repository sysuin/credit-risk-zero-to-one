"""Every path, date and seed the book uses, in one place.

A listing never types a path or a date. It imports them from here, so the book reads the
same on every machine and a reader who moves the data changes one line.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Fernhill's loan book, as its systems hold it on the morning of the book's today.
FERNHILL = DATA / "fernhill"
LOANBOOK = FERNHILL / "loanbook.duckdb"
# What the simulator knew and Fernhill never can: each borrower's true risk. Read only by
# listings about checking a method against the answer, and they say so.
TRUTH = FERNHILL / "truth.duckdb"

# Scratch space for listings: each chapter writes only under SANDBOX / "chNN".
SANDBOX = DATA / "sandbox"
# What Ballast itself writes: models, decisions, provisions, reports.
BALLAST = DATA / "ballast"

# The book's today: Monday 5 January 2026. December 2025's month end has been processed,
# so the last full month of performance is December 2025.
TODAY = dt.date(2026, 1, 5)
AS_OF = dt.date(2025, 12, 31)
FIRST_MONTH = dt.date(2016, 1, 31)

SEED = 2026
