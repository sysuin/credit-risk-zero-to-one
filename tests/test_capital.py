"""Tests for ballast.capital: the standardised tables, the IRB
formula, the output floor, the ratios, and Fernhill's book."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import fernhill
from ballast import capital
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


# ------------------------------------------------- standardised

def test_mortgage_bands_include_their_upper_edge():
    ltv = [0.30, 0.50, 0.5001, 0.60, 0.75, 0.80, 0.85, 0.90, 0.95,
           1.00, 1.20]
    rw = capital.sa_mortgage_rw(ltv)
    assert list(rw) == [0.20, 0.20, 0.25, 0.25, 0.30, 0.30, 0.40,
                        0.40, 0.50, 0.50, 0.70]


def test_companies_by_letter_then_size():
    rw = capital.sa_corporate_rw(["AAA", "BBB", "CCC", None, None],
                                 [900, 900, 900, 30, 200])
    assert list(rw) == [0.20, 0.75, 1.50, 0.85, 1.00]


def frame(**cols):
    base = {"account_id": ["X1"], "segment": ["retail"],
            "product": ["card"], "cls": ["qrre"], "drawn_cents": [1000],
            "limit_cents": [5000], "undrawn_cents": [4000],
            "collateral_cents": [0], "in_default": [False],
            "guaranteed": [0.0], "sales_m": [np.nan], "secured": [False],
            "agency": [None], "missed": [0], "pd": [0.02]}
    base.update(cols)
    return pd.DataFrame(base)


def test_standardised_card_converts_a_tenth_of_the_headroom():
    r = capital.standardised(frame())
    assert r.sa_ead.iloc[0] == pytest.approx(1000 + 0.10 * 4000)
    assert r.sa_rwa.iloc[0] == pytest.approx(0.75 * 1400)


def test_guaranteed_share_carries_no_weight():
    r = capital.standardised(frame(
        product=["sme_emergency"], cls=["other_retail"],
        limit_cents=[0], undrawn_cents=[0], guaranteed=[0.8]))
    assert r.sa_rwa.iloc[0] == pytest.approx(1000 * 0.2 * 0.75)


def test_defaulted_weight_depends_on_provisions():
    f = frame(product=["personal"], cls=["other_retail"],
              limit_cents=[0], undrawn_cents=[0], in_default=[True])
    low = pd.DataFrame({"account_id": ["X1"], "stage": [3],
                        "ecl": [100.0]})
    high = low.assign(ecl=[400.0])
    a = capital.standardised(f, low)
    b = capital.standardised(f, high)
    assert a.sa_rwa.iloc[0] == pytest.approx(900 * 1.50)
    assert b.sa_rwa.iloc[0] == pytest.approx(600 * 1.00)


# ---------------------------------------------------------- IRB

def test_correlations_by_class():
    assert capital.correlation(0.01, "mortgage") == 0.15
    assert capital.correlation(0.01, "qrre") == 0.04
    assert capital.correlation(1e-9, "corporate") == pytest.approx(
        0.24, abs=1e-6)
    assert capital.correlation(0.999, "corporate") == pytest.approx(
        0.12, abs=1e-6)
    assert capital.correlation(1e-9, "other_retail") == pytest.approx(
        0.16, abs=1e-6)
    big = capital.correlation(0.01, "corporate")
    small = capital.correlation(0.01, "corporate", sales_m=5)
    assert big - small == pytest.approx(0.04)
    assert capital.correlation(0.01, "corporate", sales_m=50) == big


def test_maturity_adjustment_is_one_at_one_year():
    assert capital.maturity_adjustment(0.02, 1.0) == pytest.approx(1)
    assert capital.maturity_adjustment(0.02, 5.0) > \
        capital.maturity_adjustment(0.02, 2.5) > 1


def test_k_is_the_conditional_loss_less_expected():
    p, lgd, r = 0.02, 0.45, 0.15
    q = norm.cdf((norm.ppf(p) + r ** 0.5 * norm.ppf(0.999))
                 / (1 - r) ** 0.5)
    assert capital.capital_k(p, lgd, "mortgage") == pytest.approx(
        lgd * (q - p))


def test_k_matches_a_simulated_quantile():
    rng = np.random.default_rng(2026)
    p, r = 0.02, 0.15
    z = rng.standard_normal(400_000)
    rate = norm.cdf((norm.ppf(p) - r ** 0.5 * z) / (1 - r) ** 0.5)
    sim = np.quantile(rate, 0.999) - p
    assert capital.capital_k(p, 1.0, "mortgage") == pytest.approx(
        sim, rel=0.03)


def test_risk_weights_rise_with_pd_and_scale():
    pds = [0.001, 0.01, 0.05]
    rw = capital.risk_weight(pds, 0.45, "corporate")
    assert np.all(np.diff(rw) > 0)
    assert capital.risk_weight(0.01, 0.45, "corporate", 2.5,
                               scaling=1.06) == pytest.approx(
        1.06 * rw[1])


def test_floors():
    assert capital.floor_pd([0.0001, 0.0001], ["qrre", "mortgage"]
                            ).tolist() == [0.0010, 0.0005]
    b = frame(product=["mortgage"], cls=["mortgage"], secured=[True],
              limit_cents=[0], undrawn_cents=[0])
    params = {"products": {"mortgage": {"lgd": 0.02, "downturn": 0.03}}}
    lg = capital.irb_lgd(b, params)
    assert lg.lgd.iloc[0] == capital.MORTGAGE_LGD_FLOOR
    lg5 = capital.irb_lgd(b, params, mortgage_floor=0.0)
    assert lg5.lgd.iloc[0] == capital.LGD_FLOOR["mortgage"]


def test_defaulted_capital_is_downturn_less_best_estimate():
    b = frame(product=["personal"], cls=["other_retail"],
              limit_cents=[0], undrawn_cents=[0], in_default=[True],
              pd=[1.0])
    r = capital.irb(b)
    assert r.k.iloc[0] == pytest.approx(r.lgd.iloc[0] - r.lgd_lr.iloc[0])
    assert r.el.iloc[0] == pytest.approx(1000 * r.lgd_lr.iloc[0])


# ---------------------------------------------------- whole bank

def test_output_floor_binds_only_below_the_line():
    assert capital.output_floor(80.0, 100.0) == 80.0
    assert capital.output_floor(60.0, 100.0) == pytest.approx(72.5)


def test_shortfall_off_cet1_excess_capped_into_tier2():
    cap = {"cet1": 100.0, "at1": 10.0, "tier2": 20.0}
    short = capital.ratios(cap, 1000.0, el_gap=-5.0, credit=800.0)
    assert short["cet1"] == pytest.approx(0.095)
    assert short["total"] == pytest.approx(0.125)
    excess = capital.ratios(cap, 1000.0, el_gap=50.0, credit=800.0)
    assert excess["cet1"] == pytest.approx(0.100)
    assert excess["total"] == pytest.approx((130 + 4.8) / 1000)


def test_requirements_add_buffers_to_every_tier():
    req = capital.requirements(countercyclical=0.0)
    assert req["cet1"] == pytest.approx(0.07)
    assert req["total"] == pytest.approx(0.105)


# ------------------------------------------------------ the book

@needs_book
def test_book_reconciles_and_reads_no_truth():
    con = fernhill.connect()
    b = capital.book(con)
    assert b.account_id.is_unique
    drawn = con.execute("""
        SELECT (SELECT sum(balance_cents) FROM performance
                WHERE month = '2025-12-31'
                  AND status IN ('up_to_date', 'arrears', 'default'))
             + (SELECT sum(drawn_cents) FROM facility_months
                WHERE month = '2025-12-31')""").fetchone()[0]
    assert b.drawn_cents.sum() == drawn
    term = b["product"] == "commercial_term"
    assert (b.loc[term, "undrawn_cents"] == 0).all()
    assert "truth" not in open(capital.__file__).read()


@needs_book
def test_saved_run_matches_its_inputs():
    path = capital.OUT / f"rwa_{capital.AS_OF}.parquet"
    if not path.exists():
        pytest.skip("Chapter 21's run has not been saved")
    r = capital.load()
    again = capital.irb(r.drop(columns=["irb_rwa", "el"]))
    assert again.irb_rwa.sum() == pytest.approx(r.irb_rwa.sum())
    assert (r.irb_ead >= r.drawn_cents - 1e-6).all()
    mort = r[r["product"] == "mortgage"]
    assert mort.irb_rwa.sum() < mort.sa_rwa.sum()
