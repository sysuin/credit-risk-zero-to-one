"""Tests for ballast.scorecard.reject: the weights, the inferred
outcomes, the weighted refit and the applicants it starts from."""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from ballast.scorecard import model, reject, sample, woe
from ballast.scorecard.binning import Bins


def _logistic(lo):
    return 1 / (1 + np.exp(-lo))


@pytest.fixture
def world():
    """Applicants with two characteristics and a known model of going
    bad; a lender books those whose first characteristic is high."""
    rng = np.random.default_rng(7)
    n = 60_000
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    bad = (rng.random(n) < _logistic(-3 - 1.0 * x1 - 0.6 * x2)
           ).astype(float)
    frame = pd.DataFrame({"x1": x1, "x2": x2, "bad": bad,
                          "margin": np.round(x1 * 20),
                          "app_id": [f"A{i:08d}" for i in range(n)]})
    frame["known"] = (x1 + rng.normal(0, 0.5, n)) > 0
    edges = [-1.0, -0.5, 0.0, 0.5, 1.0]
    tmpl = {c: Bins(c, "numeric", edges=edges) for c in ("x1", "x2")}
    return frame, tmpl


def test_weighted_woe_with_unit_weights_is_plain_woe(world):
    frame, tmpl = world
    b = tmpl["x1"]
    w = reject.weighted_woe(b, frame["x1"], frame["bad"],
                            np.ones(len(frame)))
    t = woe.woe_table(b, frame["x1"], frame["bad"].astype(int))
    assert np.allclose(list(w.values()), t["woe"].to_numpy())


def test_doubling_every_weight_changes_nothing(world):
    frame, tmpl = world
    one = reject.fit(frame, frame["bad"], None, tmpl, ["x1", "x2"])
    two = reject.fit(frame, frame["bad"], np.full(len(frame), 2.0),
                     tmpl, ["x1", "x2"])
    for k in one.coef:
        assert one.coef[k] == pytest.approx(two.coef[k], abs=1e-6)


def test_acceptance_weights_are_one_over_the_booked_share():
    margin = pd.Series([0, 1, 2, 3, 10, 11, 20, 21])
    booked = pd.Series([1, 0, 0, 0, 1, 1, 0, 0], dtype=bool)
    w = reject.acceptance_weights(margin, booked, width=10)
    assert w.iloc[0] == pytest.approx(4.0)
    assert w.iloc[4] == pytest.approx(1.0)
    assert w.iloc[6:].isna().all()          # nobody booked: no weight
    capped = reject.acceptance_weights(margin, booked, width=10, cap=3)
    assert capped.iloc[0] == pytest.approx(3.0)


def test_hard_cutoff_calls_the_riskiest_bad():
    p = pd.Series([0.05, 0.40, 0.10, 0.30, 0.15])
    bad = reject.hard_cutoff(p)             # round(1.0) = 1 bad
    assert bad.tolist() == [0, 1, 0, 0, 0]
    bad2 = reject.hard_cutoff(p, uplift=2.0)
    assert bad2.tolist() == [0, 1, 0, 1, 0]


def test_fuzzy_enters_each_row_twice_with_weights_p_and_1_minus_p():
    rows = pd.DataFrame({"app_id": ["a", "b"], "v": [1, 2]})
    out = reject.fuzzy(rows, pd.Series([0.2, 0.7]))
    assert len(out) == 4
    assert out.groupby("app_id")["weight"].sum().tolist() == [1.0, 1.0]
    bad = out[out["bad"] == 1].set_index("app_id")["weight"]
    assert bad.to_dict() == pytest.approx({"a": 0.2, "b": 0.7})


def test_parcel_draws_at_the_band_rate(world):
    frame, _ = world
    rng = np.random.default_rng(3)
    known_score = pd.Series(np.repeat([550.0, 610.0], 1000))
    known_bad = pd.Series(np.r_[np.ones(200), np.zeros(800),
                                np.ones(20), np.zeros(980)])
    score = pd.Series(np.repeat([550.0, 610.0], 20_000))
    b = reject.parcel(score, known_score, known_bad, [580], rng)
    assert b[:20_000].mean() == pytest.approx(0.20, abs=0.01)
    assert b[20_000:].mean() == pytest.approx(0.02, abs=0.005)


def test_fuzzy_without_outside_evidence_gives_back_the_same_model(
        world):
    """Fuzzy augmentation with the booked-only model's own rates
    adds no information: the refit barely moves."""
    frame, tmpl = world
    cols = ["x1", "x2"]
    acc = frame[frame["known"]]
    unk = frame[~frame["known"]]
    base = reject.fit(acc, acc["bad"], None, tmpl, cols)
    t = reject.training_set("fuzzy", acc, unk, base=base)
    again = reject.fit(t, t["bad"], t["weight"], tmpl, cols)
    for k in cols:
        assert again.coef[k] == pytest.approx(base.coef[k], abs=0.05)


def test_retro_rows_only_where_a_loan_was_opened(world):
    frame, _ = world
    acc = frame[frame["known"]].head(10)
    unk = frame[~frame["known"]].head(3)
    retro = pd.DataFrame({"app_id": unk["app_id"].tolist(),
                          "opened_elsewhere": [True, False, True],
                          "bad_elsewhere": [1.0, np.nan, 0.0]})
    t = reject.training_set("bureau retro", acc, unk, retro_rows=retro)
    assert len(t) == 12
    assert t["bad"].iloc[10:].tolist() == [1.0, 0.0]


def test_save_and_load_round_trip(world, tmp_path):
    frame, tmpl = world
    r = reject.fit(frame, frame["bad"], None, tmpl, ["x1", "x2"])
    reject.save_refit(r, "t", path=tmp_path)
    back = reject.load_refit("t", path=tmp_path)
    assert np.allclose(back.p_bad(frame), r.p_bad(frame), atol=1e-5)


def test_ballast_never_reads_the_truth():
    src = inspect.getsource(reject)
    assert "truth=True" not in src and "truth.duckdb" not in src


def test_applicants_reconcile_with_chapter_7():
    """Reads the loan book: every development applicant is there, the
    unknowns are split 70/30, and ignoring them refits Mark II."""
    if not (sample.MARK2 / "model.json").exists():
        pytest.skip("Mark II has not been saved")
    a = reject.applicants()
    dev = a[a["period"] == "development"]
    assert len(dev) == 52_445
    unk = dev[~dev["known"]]
    assert (unk["split"] == "holdout").mean() == pytest.approx(0.3,
                                                               abs=1e-4)
    f = reject.frames(a)
    r = reject.fit(f["accepts"], f["accepts"]["bad"])
    saved = model.load_model()["coef"]
    for k, v in saved.items():
        assert r.coef[k] == pytest.approx(v, abs=1e-4)
