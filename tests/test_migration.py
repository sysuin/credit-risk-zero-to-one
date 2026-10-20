"""Tests for ballast.commercial.migration: the panel, the matrix,
default rates against the scale, and projection."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def toy_reviews() -> pd.DataFrame:
    return pd.DataFrame({
        "company_id": ["A", "A", "A", "B", "B", "C"],
        "review_date": pd.to_datetime(
            ["2020-03-31", "2021-03-31", "2022-03-31",
             "2020-03-31", "2021-03-31", "2020-03-31"]),
        "grade": [3, 4, 4, 8, 9, 5],
        "default_12m": [0, 0, 0, 0, 1, 0]})


def test_panel_states():
    p = mg.panel(toy_reviews())
    got = dict(zip(zip(p.company_id, p.review_date.dt.year),
                   p.after))
    assert got[("A", 2020)] == "4" and got[("A", 2021)] == "4"
    assert got[("B", 2020)] == "9" and got[("B", 2021)] == "D"
    # the last review of A and C's only one have no year after
    assert ("A", 2022) not in got and ("C", 2020) not in got


def test_matrix_rows_sum_to_one():
    p = mg.panel(toy_reviews())
    m = mg.matrix(p)
    assert list(m.columns) == mg.STATES
    filled = m.dropna()
    assert np.allclose(filled.sum(axis=1), 1.0)
    c = mg.matrix(p, shares=False)
    assert c.loc["9", "D"] == 1 and c.values.sum() == len(p)


def test_summary_shares():
    p = mg.panel(toy_reviews())
    s = mg.summary(p)
    assert s["moves"] == 3
    assert s["stayed"] == pytest.approx(1 / 3)
    assert s["one"] == pytest.approx(2 / 3)


def test_interval_and_default_rates():
    lo, hi = mg.interval(0, 100)
    assert lo == 0.0 and hi == pytest.approx(0.0362, abs=1e-3)
    lo, hi = mg.interval(5, 100)
    assert lo < 0.05 < hi
    rv = pd.DataFrame({"grade": [10] * 10 + [1] * 10,
                       "default_12m": [1, 1] + [0] * 18})
    t = mg.default_rates(rv)
    assert t.loc[10, "observed"] == pytest.approx(0.2)
    assert t.loc[10, "expected"] == pytest.approx(2.0)
    assert t.loc[1, "defaults"] == 0 and t.loc[5, "n"] == 0


def test_project_compounds():
    m = pd.DataFrame(0.0, index=mg.STATES[:-1], columns=mg.STATES)
    for g in mg.STATES[:-1]:
        m.loc[g, g], m.loc[g, "D"] = 0.9, 0.1
    pr = mg.project(m, 3)
    assert pr.loc["5", 1] == pytest.approx(0.1)
    assert pr.loc["5", 3] == pytest.approx(1 - 0.9 ** 3)


@needs_book
def test_book_matrix():
    con = fernhill.connect()
    rv = rt.reviews(con)
    p = mg.panel(rv)
    c = mg.matrix(p, shares=False)
    assert c["D"].sum() == 35
    s = mg.summary(p)
    assert s["two"] == 0.0 and 0.4 < s["stayed"] < 0.6
    t = mg.default_rates(rv[rv.window_complete])
    assert t.defaults.sum() == 35
