"""Chapter 23's one shortcut: every booked personal loan scored by
Mark II-R (Chapter 18's `personal_loans`), kept under the chapter's
sandbox once a listing has built it, and built again whenever the loan
book is newer than the copy. Scoring every application takes minutes
on a busy machine, and most of this chapter's listings need it."""
import pandas as pd

import fernhill
from ballast.config import LOANBOOK, SANDBOX
from ballast.parameters import pd as pdm

LOANS = SANDBOX / "ch23" / "loans.parquet"


def loans(con=None) -> pd.DataFrame:
    stale = (not LOANS.exists()
             or LOANS.stat().st_mtime < LOANBOOK.stat().st_mtime)
    if stale:
        LOANS.parent.mkdir(parents=True, exist_ok=True)
        pdm.personal_loans(con or fernhill.connect()).to_parquet(LOANS)
    return pd.read_parquet(LOANS)
