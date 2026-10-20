"""Tests for ballast.commercial.sme: SME-1's points, the sample and
the emergency loans' losses."""
from __future__ import annotations

import pandas as pd
import pytest

import fernhill
from ballast.commercial import sme
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def test_sme1_points_by_hand():
    apps = pd.DataFrame({
        "owner_bureau_score": [650, 300, 900],
        "business_score": [50, 10, 100],
        "years_trading": [1, 3, 10],
        "existing_debt_cents": [0, 20_000_00, 40_000_00],
        "amount_requested_cents": [10_000_00, 10_000_00, 20_000_00],
        "turnover_cents": [100_000_00, 100_000_00, 100_000_00],
        "secured": [False, False, True]})
    p = sme.sme1_points(apps)
    assert list(p.owner) == [50, 0, 100]
    assert list(p.years) == [0, 20, 35]
    assert list(p.borrowing) == [40, 12, 0]
    assert list(p.security) == [0, 0, 20]
    assert list(p.total) == [135, 41, 245]


@needs_book
def test_sme1_matches_the_book():
    con = fernhill.connect()
    apps = con.execute("SELECT * FROM sme_applications").df()
    assert (sme.sme1_points(apps).total == apps.sme1_score).all()


@needs_book
def test_sample_and_losses():
    con = fernhill.connect()
    s = sme.sample(con)
    assert len(s) == 3648 and s.bad.sum() == 236
    assert s.owner_score.between(300, 850).all()
    assert s.ob_balance.notna().sum() == s.ob.sum()
    L = sme.emergency_losses(con)
    c = L[L.charged_off]
    # the guarantee pays 80% of the exposure on charged-off loans
    # (a few loans' first default under the 2021 definition is a
    # month or two away from the one the claim was made on)
    paid = c[c.guarantee > 0]
    ratio = paid.guarantee / paid.ead_cents
    assert ratio.median() == pytest.approx(0.80, abs=1e-3)
    assert ratio.between(0.79, 0.81).mean() > 0.98
