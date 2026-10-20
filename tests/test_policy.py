"""Tests for ballast.decision.policy: Fernhill's rules, Mark I's points
table, the cut-off history, amounts, card limits and line increases."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from ballast.config import LOANBOOK
from ballast.decision import policy as pol


def _app(**kw):
    """One personal-loan applicant, ordinary in every way unless told."""
    row = dict(product="personal", bureau_hit=True, bureau_score=650.0,
               bureau_version="v3", revolving_utilisation=0.30,
               enquiries_6m=0, worst_status_24m=0, public_records=0,
               other_payments_cents=20_000, stated_income_cents=6_000_000,
               amount_requested_cents=1_000_000, term_requested_months=36,
               employment="employed", employment_months=48,
               housing="renter", address_months=40, age=40)
    row.update(kw)
    return pd.DataFrame([row])


def test_cutoff_history():
    assert pol.cutoff_on(dt.date(2016, 1, 1)) == 560
    assert pol.cutoff_on(dt.date(2020, 3, 31)) == 575
    assert pol.cutoff_on(dt.date(2020, 4, 1)) == 610
    assert pol.cutoff_on(dt.date(2021, 2, 1)) == 525
    assert pol.cutoff_on(dt.date(2022, 6, 30)) == 525
    assert pol.cutoff_on(dt.date(2022, 7, 1)) == 580
    assert pol.cutoff_on(dt.date(2025, 6, 1), "card") == 585
    assert pol.period_of(dt.date(2021, 3, 1))[2] == 0.55
    with pytest.raises(ValueError):
        pol.period_of(dt.date(2015, 12, 31))


def test_rules_fire_in_order():
    rows = pd.concat([
        _app(),
        _app(worst_status_24m=90, public_records=1),     # both: first
        _app(public_records=2),
        _app(bureau_hit=False, bureau_score=np.nan, age=22),
        _app(bureau_hit=False, bureau_score=np.nan, age=30),
        _app(other_payments_cents=2_500_000),
    ], ignore_index=True)
    got = pol.policy_reason(rows).tolist()
    assert got == [None, "recent_serious_arrears", "public_record",
                   "thin_file", None, "affordability"]


def test_dti_uses_the_assessment_rate():
    a = _app()
    pay = pol.instalment(1_000_000, 36, 10.9)
    assert pol.dti_at_decision(a).iloc[0] == pytest.approx(
        (20_000 + pay) / 500_000)
    card = _app(product="card")
    assert pol.dti_at_decision(card).iloc[0] == pytest.approx(0.04)


def test_band_points_edges_are_upper_bounds():
    edges, pts = pol.MARK1["bureau_score"]
    got = pol.band_points([519, 520, 559, 560, 760, 850], edges, pts)
    assert got.tolist() == [0, 22, 22, 41, 116, 116]


def test_mark1_scores_one_applicant_by_hand():
    a = _app()
    # bureau 650: 74; util 0.30: 55; enquiries 0: 60; worst 0: 58;
    # dti about 0.10: 60; employed 48 months: 50; renter 40;
    # address 40 months: 53; age 40: 50.
    assert pol.mark1_score(a).iloc[0] == 140 + 74 + 55 + 60 + 58 + 60 \
        + 50 + 40 + 53 + 50
    nofile = _app(bureau_hit=False, bureau_score=np.nan,
                  revolving_utilisation=np.nan)
    lines = pol.mark1_lines(nofile).iloc[0]
    assert lines["bureau_score"] == pol.MARK1_NO_FILE
    assert lines["revolving_utilisation"] == 44
    retired = _app(employment="retired", employment_months=np.nan)
    assert pol.mark1_lines(retired).iloc[0]["employment_months"] == 52


def test_mark1_refuses_mortgages():
    with pytest.raises(ValueError):
        pol.mark1_score(_app(product="mortgage"))


def test_v2_ruler_moves_only_version_3_and_lowers_scores():
    mapping = pd.Series(np.arange(300, 851) + 30,
                        index=np.arange(300, 851))
    v3 = _app(bureau_score=650.0)
    v2 = _app(bureau_score=650.0, bureau_version="v2")
    both = pd.concat([v3, v2], ignore_index=True)
    got = pol.mark1_on_v2_ruler(both, mapping)
    assert got.iloc[1] == pol.mark1_score(v2).iloc[0]
    # 650 on version 3 is 620 on version 2: one band lower.
    assert got.iloc[0] == pol.mark1_score(v3).iloc[0] - (74 - 58)


def test_offered_amount_cuts_to_80_percent_near_the_limit():
    got = pol.offered_amount([1_000_000, 1_000_000, 1_234_500],
                             [0.30, 0.46, 0.47], 0.50)
    assert got.tolist() == [1_000_000, 800_000, 990_000]


def test_card_limit_grid():
    got = pol.card_limit([4_000_000, 4_000_000, 4_000_000, 300_000,
                          20_000_000], [600, 640, 680, 600, 700])
    assert got.tolist() == [280_000, 480_000, 720_000, 50_000,
                            2_000_000]


def test_line_increase_rule():
    got = pol.line_increase(
        limit_cents=[480_000, 500_000, 500_000, 500_000, 2_900_000],
        balance_cents=[300_000, 200_000, 300_000, 300_000, 2_000_000],
        missed=[0, 0, 1, 0, 0], months_on_book=[12, 12, 12, 13, 18])
    assert got.tolist() == [600_000, 500_000, 500_000, 500_000,
                            3_000_000]
    refused = pol.line_increase([500_000], [300_000], [0], [12],
                                checks_passed=[False])
    assert refused.tolist() == [500_000]


def test_policy_zone_and_round_trip(tmp_path):
    p = pol.Policy("test", "mark2/scorecard", cutoff=554, refer_below=4,
                   refer_above=4)
    assert p.zone([549, 550, 557, 558]).tolist() == [
        "decline", "refer", "refer", "approve"]
    pol.save_policy(p, tmp_path)
    assert pol.load_policy(tmp_path) == p


def test_reproduces_fernhill_records():
    """Reads the loan book: Mark I and the rules match every record."""
    if not LOANBOOK.exists():
        pytest.skip("no loan book")
    from ballast import data
    raw = data.load_applications(unknowns=False)
    apps = raw[raw["product"].astype(str).isin(["personal", "card",
                                                 "auto"])]
    assert (pol.mark1_score(apps) == apps["mark1_score"]).all()
    limit = np.array([pol.period_of(d)[2] for d in apps["app_date"]])
    rule = pol.policy_reason(apps, limit)
    rec = apps["decline_reason"].astype(object)
    recorded = rec.isin(pol.RULES)
    assert (rule[recorded] == rec[recorded]).all()
    assert rule[~recorded].isna().sum() + rec.eq("fraud_check")[
        rule.notna() & ~recorded].sum() == (~recorded).sum()
