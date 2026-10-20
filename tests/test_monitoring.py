"""Tests for ballast.monitoring: stability measures and their noise,
drift tables, the behavioural score, the watchlist's record, and the
pack's width."""
from __future__ import annotations

import datetime as dt
import inspect

import numpy as np
import pandas as pd
import pytest

from ballast import monitoring as mon
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="needs the loan book")


def test_psi_is_zero_for_the_same_distribution_and_grows_with_a_shift():
    rng = np.random.default_rng(1)
    ref = rng.normal(600, 60, 20_000)
    assert mon.psi(ref, ref) == pytest.approx(0.0)
    small = mon.psi(ref, ref + 10)
    large = mon.psi(ref, ref + 30)
    assert 0 < small < large


def test_psi_by_hand():
    e = np.array([0.5, 0.5])
    a = np.array([0.6, 0.4])
    want = 0.1 * np.log(0.6 / 0.5) + (-0.1) * np.log(0.4 / 0.5)
    assert mon.psi_from_shares(e, a) == pytest.approx(want)


def test_an_empty_band_is_floored_not_infinite():
    assert np.isfinite(mon.psi_from_shares([0.5, 0.5], [1.0, 0.0]))


def test_psi_table_parts_add_up_to_the_psi():
    rng = np.random.default_rng(2)
    ref = rng.integers(400, 700, 5_000)
    now = rng.integers(420, 720, 600)
    t = mon.psi_table(ref, now)
    assert t["part"].sum() == pytest.approx(mon.psi(ref, now))
    assert t["reference"].sum() == pytest.approx(1.0)


def test_noise_level_is_exceeded_about_as_often_as_promised():
    """With nothing changed, the 99% noise level is crossed rarely."""
    rng = np.random.default_rng(3)
    ref = rng.normal(0, 1, 7_000)
    edges = mon.decile_edges(ref)
    level = mon.psi_noise(600, 7_000)
    over = sum(mon.psi(ref, rng.normal(0, 1, 600), edges) > level
               for _ in range(400))
    assert over / 400 < 0.04
    assert mon.psi_noise(6_000, 7_000) < level      # more data, less noise


def test_characteristic_shifts_add_up_to_the_score_shift():
    ref = pd.DataFrame({"a": [10, 20, 20, 30], "b": [5, 5, 0, 0]})
    now = pd.DataFrame({"a": [30, 30, 20, 30], "b": [5, 0, 0, 0]})
    t = mon.characteristic_analysis(ref, now)
    shift = now.sum(axis=1).mean() - ref.sum(axis=1).mean()
    assert t["shift"].sum() == pytest.approx(shift)
    assert t.iloc[0]["line"] == "a"                 # moved most first


def test_monthly_stability_rolling_reference_absorbs_a_step():
    months = pd.period_range("2018-01", "2020-12", freq="M")
    rng = np.random.default_rng(4)
    rows = []
    for m in months:
        shift = 30 if m >= pd.Period("2019-07", "M") else 0
        rows += [(m, v) for v in rng.normal(570 + shift, 60, 600)]
    df = pd.DataFrame(rows, columns=["m", "v"])
    roll = mon.monthly_stability(df["v"], df["m"]).set_index("month")
    fixed = mon.monthly_stability(df["v"], df["m"],
                                  reference=df["m"] < pd.Period("2019-01",
                                                                "M")
                                  ).set_index("month")
    assert roll.loc["2019-07", "psi"] > roll.loc["2019-07", "noise"]
    assert roll.loc["2020-12", "psi"] < roll.loc["2020-12", "noise"]
    assert fixed.loc["2020-12", "psi"] > fixed.loc["2020-12", "noise"]


def test_calibration_drift_flags_a_broken_promise():
    promised = np.full(1_000, 0.02)
    bad = np.zeros(1_000, dtype=int)
    bad[:80] = 1                                    # 8% seen
    period = np.repeat(["A", "B"], 500)
    t = mon.calibration_drift(promised, bad, period).set_index("period")
    assert t.loc["A", "outside"]                    # 16% against 2%
    assert not t.loc["B", "outside"] or t.loc["B", "bads"] == 0
    lo, hi = mon.binomial_interval(10, 500)
    assert lo < 0.02 < hi


def test_behaviour_score_points_follow_risk():
    rng = np.random.default_rng(5)
    n = 20_000
    f = pd.DataFrame({
        "product": "card",
        "months_on_book": rng.integers(1, 60, n),
        "missed_now": rng.choice([0, 0, 0, 0, 1, 2], n),
        "utilisation": rng.uniform(0, 1, n),
        "application_score": rng.integers(500, 700, n)})
    logit = (-4 + 2.5 * f["missed_now"] + 2 * f["utilisation"]
             - 0.01 * (f["application_score"] - 600))
    f["bad"] = (rng.uniform(0, 1, n) < 1 / (1 + np.exp(-logit))
                ).astype(float)
    b = mon.fit_behaviour(f, "card")
    t = b.table
    assert t["missed_now"]["0"] > t["missed_now"]["1"] > \
        t["missed_now"]["2"] == 0
    assert t["utilisation"]["<10%"] > t["utilisation"]["90%+"]
    assert min(t["application"].values()) == 0
    s = b.score(f)
    assert (s == b.base + b.line_points(f).sum(axis=1)).all()


def test_watch_record_counts_hits_and_false_alarms():
    month = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-01-31",
                            "2020-02-29"])
    p = pd.DataFrame({"company_id": ["A", "A", "B", "B"],
                      "month": month,
                      "default_month": pd.to_datetime(
                          ["2020-06-30", "2020-06-30", None, None]),
                      "default_12m": [1.0, 1.0, 0.0, 0.0]})
    flags = pd.DataFrame({"x": [False, True, True, False]})
    r = mon.watch_record(p, flags).iloc[0]
    assert r["months"] == 2 and r["companies"] == 2
    assert r["hit_rate"] == pytest.approx(0.5)
    assert r["caught"] == 1 and r["defaults"] == 1
    assert r["false_alarms"] == 1
    assert r["warning"] == 4


def test_table_refuses_to_run_off_the_page():
    with pytest.raises(ValueError):
        mon.table(("a",), [("x" * 70,)], (70,))
    assert mon.table(("a", "b"), [("x", "1")], (5, 4)) == ["a       b",
                                                          "x       1"]


def test_monitoring_never_reads_the_truth_or_the_monitoring_table():
    src = inspect.getsource(mon)
    assert "truth" not in src
    assert "applicant_monitoring" not in src


@needs_book
def test_july_2019_on_the_real_book():
    import fernhill
    con = fernhill.connect()
    a = con.execute("""SELECT app_date, mark1_score FROM applications
                       WHERE product = 'personal' AND app_date
                       BETWEEN '2018-07-01' AND '2019-07-31'""").df()
    d = a["app_date"].astype(str)
    ref, jul = a[d < "2019-07-01"].mark1_score, a[d >= "2019-07-01"] \
        .mark1_score
    value = mon.psi(ref, jul)
    assert value < mon.PSI_AMBER                    # green by the rule
    assert value > mon.psi_noise(len(jul), len(ref))   # but not noise


@needs_book
def test_business_panel_stops_before_default():
    import fernhill
    p = mon.business_panel(fernhill.connect(),
                           start=dt.date(2020, 1, 31),
                           end=dt.date(2020, 12, 31))
    assert not (p["default_month"] <= p["month"]).any()
    assert p["default_12m"].dropna().isin([0, 1]).all()
