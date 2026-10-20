"""Fernhill Bank's loan book: a stand-in for the systems a lender runs.

This package is not the reader's code. `generate.py` builds the loan book from a seed;
`verify.py` proves it has the properties the chapters rely on. A listing reaches the data
through `connect()`, read-only, so no chapter can damage what the next one reads.
"""
from __future__ import annotations

import duckdb

from ballast.config import LOANBOOK, TRUTH


def connect(truth: bool = False) -> duckdb.DuckDBPyConnection:
    """The loan book, read-only. `truth=True` opens the simulator's answers instead."""
    path = TRUTH if truth else LOANBOOK
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run `make data` first")
    return duckdb.connect(str(path), read_only=True, config={"threads": 1})
