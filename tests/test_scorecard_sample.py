"""Tests for ballast.scorecard.sample: Mark II's sample, on the loan book."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast import data
from ballast.config import LOANBOOK
from ballast.scorecard import sample

pytestmark = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="needs the loan book")


@pytest.fixture(scope="module")
def apps():
    return data.load_applications()


@pytest.fixture(scope="module")
def s(apps):
    return sample.build_sample(apps=apps)


def test_one_row_per_booked_personal_loan(s, apps):
    booked = apps[(apps["product"] == "personal")
                  & (apps["outcome"] == "booked")
                  & (apps["app_date"] >= sample.DEV_FROM)
                  & (apps["app_date"] <= sample.OOT_TO)]
    assert len(s) == len(booked)
    assert s["app_id"].is_unique and s["account_id"].is_unique
    assert s["account_id"].str.startswith("PL").all()


def test_outcomes_follow_worst_missed(s):
    assert (s.loc[s["outcome"] == "bad", "worst_missed"] >= 3).all()
    assert (s.loc[s["outcome"] == "indeterminate",
                  "worst_missed"] == 2).all()
    assert (s.loc[s["outcome"] == "good", "worst_missed"] <= 1).all()
    assert (s["bad"] == (s["outcome"] == "bad")).all()


def test_splits(s):
    dev = s[s["split"] != "out_of_time"]
    assert (dev["app_date"] <= sample.DEV_TO).all()
    oot = s[s["split"] == "out_of_time"]
    assert (oot["app_date"] >= sample.OOT_FROM).all()
    share = (dev["split"] == "holdout").mean()
    assert share == pytest.approx(sample.HOLDOUT_SHARE, abs=0.001)
    assert (s["fit"] == ((s["split"] == "train")
                         & (s["outcome"] != "indeterminate"))).all()


def test_holdout_is_the_same_every_time(s):
    ids = s.loc[s["split"] != "out_of_time", "app_id"]
    a = sample.holdout(ids)
    b = sample.holdout(ids.sample(frac=1, random_state=3))
    assert set(ids[a]) == set(ids.loc[b.index][b])


def test_window_is_twelve_payments(apps):
    con = fernhill.connect()
    o = sample.outcomes(con)
    one = o[o["worst_missed"] >= 3].iloc[0]
    got = con.execute(
        "SELECT max(missed) FROM performance WHERE account_id = ? "
        "AND datediff('month', ?, month) BETWEEN 1 AND 12",
        [one["account_id"], one["open_date"]]).fetchone()[0]
    assert got == one["worst_missed"]


def test_holidays_only_around_2020(s):
    h = s[s["holiday"]]
    assert len(h) > 0
    assert (h["app_date"] >= pd.Timestamp("2019-01-01").date()).all()
    assert (h["app_date"] <= pd.Timestamp("2020-12-31").date()).all()


def test_bureau_map(apps):
    m = sample.bureau_map(apps)
    assert m.index.min() == 300 and m.index.max() == 850
    assert m.is_monotonic_increasing
    h1 = apps[(apps["app_date"] >= sample.V2_HALF[0])
              & (apps["app_date"] <= sample.V2_HALF[1])
              & apps["bureau_hit"]]
    h3 = apps[(apps["app_date"] >= sample.V3_HALF[0])
              & (apps["app_date"] <= sample.V3_HALF[1])
              & apps["bureau_hit"]]
    mapped = h1["bureau_score"].astype(int).map(m)
    assert mapped.mean() == pytest.approx(
        h3["bureau_score"].astype(float).mean(), abs=1.0)


def test_scores_are_on_version_3(s, apps):
    v2 = apps.loc[apps["bureau_version"] == "v2", "app_id"]
    sub = s[s["app_id"].isin(v2)]
    raw = apps.set_index("app_id").loc[sub["app_id"], "bureau_score"]
    assert (sub["bureau_score"].to_numpy()
            > raw.astype(float).to_numpy()).mean() > 0.95


def test_characteristics_known_at_application(s):
    for col in s.columns:
        assert not col.startswith("ob_")
    for banned in ("gender", "mark1_score", "offered_rate_pct",
                   "decision", "income_verified"):
        assert banned not in s.columns
    assert set(sample.CHARACTERISTICS) <= set(s.columns)


def test_no_file_is_missing_everywhere_bureau(s):
    nofile = s["bureau_score"].isna()
    for col, label in sample.MISSING_LABEL.items():
        if label == sample.NO_FILE:
            assert (s.loc[nofile, col].isna()).all(), col
            assert s.loc[~nofile, col].notna().all(), col


def test_dti(s):
    one = s.iloc[0]
    assert 0 < one["dti"] < 2
    assert np.isfinite(s["dti"].dropna()).all()


def test_save_and_load(tmp_path, s):
    files = sample.save_sample(s, tmp_path)
    assert all(f.exists() for f in files)
    back = sample.load_sample(tmp_path)
    assert len(back) == len(s)
    assert back["bad"].sum() == s["bad"].sum()
    assert back.attrs["bureau_map"].equals(s.attrs["bureau_map"])
    pd.testing.assert_series_equal(back["bureau_score"].astype(float),
                                   s["bureau_score"].astype(float))
