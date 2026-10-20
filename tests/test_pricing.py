"""Tests for ballast.pricing: funding, rates from the book, expected
cash flows, the floor and its pieces, RAROC, take-up and the grid."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ballast import pricing

MARKET = {"policy_rate_pct": 4.0, "cost_of_funds_pct": 3.5,
          "swap_2y_pct": 4.4, "swap_5y_pct": 4.0}
FREE = pricing.Costs(opex_pct=0.0, capital_pct=0.0, hurdle_pct=0.0,
                     lgd=0.0)


def test_monthly_hazard_compounds_to_the_year():
    h = pricing.monthly_hazard(0.12)
    assert 1 - (1 - h) ** 12 == pytest.approx(0.12)
    assert pricing.annual_rate(1, 100) == pytest.approx(1 - 0.99 ** 12)


def test_ftp_reads_the_curve_and_adds_the_spread():
    spread = -0.5
    assert pricing.ftp_pct(MARKET, 0) == pytest.approx(4.0 + spread)
    assert pricing.ftp_pct(MARKET, 24) == pytest.approx(4.4 + spread)
    assert pricing.ftp_pct(MARKET, 12) == pytest.approx(4.2 + spread)
    assert pricing.ftp_pct(MARKET, 120) == pytest.approx(4.0 + spread)


def test_expected_flows_account_for_every_cent():
    f = pricing.expected_flows(1_000_000, 12.0, 36, 0.05, 0.2, 0.6)
    back = f["principal"].sum() + f["recovered"].sum() + f["loss"].sum()
    assert back == pytest.approx(1_000_000, rel=1e-9)
    assert (np.diff(f["alive"]) < 0).all()
    assert f["balance"].iloc[0] == 1_000_000


def test_no_risk_no_prepayment_is_the_schedule():
    f = pricing.expected_flows(1_000_000, 12.0, 24, 0.0, 0.0, 0.6)
    assert f["loss"].sum() == 0
    assert f["principal"].sum() == pytest.approx(1_000_000)
    assert pricing.expected_life(f) == pytest.approx(
        f["balance"].sum() / 1_000_000)


def test_prepayment_shortens_the_life():
    slow = pricing.expected_flows(1_000_000, 12.0, 36, 0.01, 0.0, 0.6)
    fast = pricing.expected_flows(1_000_000, 12.0, 36, 0.01, 0.3, 0.6)
    assert pricing.expected_life(fast) < pricing.expected_life(slow)


def test_without_costs_or_risk_the_floor_is_the_transfer_price():
    r = pricing.floor_rate(1_000_000, 36, 0.0, 0.0, MARKET, FREE)
    v = pricing.value(1_000_000, r, 36, 0.0, 0.0, MARKET, FREE)
    assert r == pytest.approx(v.ftp_pct, abs=0.02)


def test_waterfall_adds_up_and_raroc_is_the_hurdle_at_the_floor():
    c = pricing.Costs()
    w = pricing.waterfall(1_200_000, 36, 0.03, 0.2, MARKET, c)
    parts = w["funding"] + w["operating"] + w["capital"] \
        + w["expected_loss"]
    assert parts == pytest.approx(w["floor"])
    v = pricing.value(1_200_000, w["floor"], 36, 0.03, 0.2, MARKET, c)
    assert v.economic == pytest.approx(0, abs=1)
    assert v.raroc == pytest.approx(c.hurdle_pct / 100, abs=1e-4)
    assert w["expected_loss"] == pytest.approx(3 * c.lgd, abs=0.15)


def test_riskier_loans_need_dearer_floors():
    floors = [pricing.floor_rate(1_200_000, 36, pd_, 0.2, MARKET)
              for pd_ in (0.005, 0.02, 0.08)]
    assert floors[0] < floors[1] < floors[2]


def test_fit_hazard_recovers_a_known_slope():
    rng = np.random.default_rng(3)
    score = rng.integers(520, 660, 40_000)
    months = np.full(len(score), 24)
    rate = np.exp(18.0 - 0.04 * score)
    events = rng.poisson(rate * months)
    h = pricing.fit_hazard(score, events, months)
    assert h.b == pytest.approx(-0.04, abs=3 * h.se_b + 1e-3)
    assert h.annual(600) < h.annual(560)


def test_take_up_moves_the_right_way_and_inverts():
    up = pricing.shift_take_up(0.6, -0.4, [-1, 0, 1])
    assert up[0] > up[1] > up[2]
    assert up[1] == pytest.approx(0.6)
    assert pricing.logit(up[2]) - pricing.logit(0.6) == \
        pytest.approx(-0.4)


def test_fit_take_up_recovers_a_randomised_slope():
    rng = np.random.default_rng(5)
    change = rng.choice([-1.5, 0.0, 1.5], 30_000)
    took = rng.random(len(change)) < pricing.shift_take_up(
        0.6, -0.4, change)
    r = pricing.fit_take_up(took, change)
    lo, hi = r.conf_int().loc["change"]
    assert lo < -0.4 < hi


def test_best_rate_trades_take_up_against_margin():
    best, t = pricing.best_rate(np.arange(5, 20.01, 0.5), 0.6, -0.4,
                                10.0, lambda r: r - 6.0)
    assert 7 < best < 20
    assert t["per_approval"].max() == pytest.approx(
        t.loc[t["rate"] == best, "per_approval"].iloc[0])


def test_grid_tiers_edges_and_pass_through():
    g = pricing.Grid(edges=(565, 580), rates=(18.0, 14.0, 10.0),
                     at_ftp_pct=3.0)
    assert g.tier([550, 564, 565, 579, 580, 640]).tolist() == \
        [0, 0, 1, 1, 2, 2]
    assert g.rate([570]).tolist() == [14.0]
    assert g.rate([570], ftp=4.0).tolist() == [15.0]
    assert g.labels(550, 652) == ["550-564", "565-579", "580-652"]


def test_monotone_never_lets_risk_be_cheaper():
    assert pricing.monotone([12.0, 14.0, 11.0]) == [14.0, 14.0, 11.0]


def test_pricing_round_trips(tmp_path):
    p = pricing.Pricing(
        pricing.Grid((565,), (15.0, 11.0), 3.3, 15.0),
        pricing.Hazard(-1.0, -0.04, 0.001), pricing.Hazard(-2.0, -0.01),
        pricing.Costs(), MARKET, {"note": "test"})
    path = pricing.save_pricing(p, tmp_path / "p.json")
    assert pricing.load_pricing(path) == p
    q = pricing.price_application(p, 600, 1_200_000, 36)
    assert q["tier"] == 2 and q["rate"] == pytest.approx(
        11.0 + pricing.ftp_pct(MARKET, 15.0) - 3.3, abs=0.01)


def test_pricing_never_reads_the_truth():
    text = Path(pricing.__file__).read_text()
    assert "truth" not in text.replace("Ballast never reads", "")
