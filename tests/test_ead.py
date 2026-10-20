"""Tests for ballast.parameters.ead: the EAD formula, the CCF fit and
what the loan book says about drawing before default."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast.config import LOANBOOK
from ballast.parameters import ead

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def sample():
    return pd.DataFrame({
        "b0": [100, 400, 950, 200], "l0": [1000, 1000, 1000, 1000],
        "ead": [370, 580, 900, 470]}).assign(
        u0=lambda d: d["b0"] / d["l0"],
        ccf=lambda d: (d["ead"] - d["b0"]) / (d["l0"] - d["b0"]))


def test_pooled_ccf_is_drawn_over_headroom():
    s = sample()
    drawn = (370 - 100) + (580 - 400) + (900 - 950) + (470 - 200)
    room = 900 + 600 + 50 + 800
    assert ead.pooled_ccf(s) == pytest.approx(drawn / room)


def test_fit_floors_and_bands():
    t = ead.fit_ccf(sample())
    assert t.loc["0%-30%", "n"] == 2
    assert t.loc["0%-30%", "ccf"] == pytest.approx(540 / 1700)
    assert t.loc["90%+", "ccf_raw"] < 0 == t.loc["90%+", "ccf"]


def test_exposure_formula():
    t = ead.fit_ccf(sample())
    out = ead.exposure([100, 950, 0], [1000, 1000, 0], t)
    assert out[0] == pytest.approx(100 + 540 / 1700 * 900)
    assert out[1] == 950                  # never below the balance
    assert out[2] == 0
    assert np.all(out >= [100, 950, 0])


@needs_book
def test_cards_draw_down_before_default():
    con = fernhill.connect()
    u = ead.utilisation_before(con, products=("card",),
                               months=(12, 0)).set_index("before")
    assert u.loc[0, "utilisation"] > u.loc[12, "utilisation"] + 0.1
    assert u.loc[12, "utilisation"] > ead.performing_utilisation(
        con, "card")
    s = ead.ccf_sample(con, "card")
    assert 0.2 < ead.pooled_ccf(s[s["missed0"] == 0]) < 0.4


@needs_book
def test_revolvers_use_the_defaulted_row():
    con = fernhill.connect()
    s = ead.revolver_sample(con)
    assert s["facility_id"].is_unique
    assert (s["ead"] / s["l1"]).mean() > 0.8
