"""Tests for ballast.decision.engine: the steps, in order, for one
application and for many, and the reasons each decline carries."""
from __future__ import annotations

import inspect

import pandas as pd
import pytest

from ballast.config import LOANBOOK
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import reject

POLICY = pol.Policy("Mark II-R", "reject/mark2_retro_ws", cutoff=554,
                    refer_below=4, refer_above=4)
SHORT = pd.Series({"bureau_file": 0, "enquiries_6m": 9,
                   "bureau_score": 30, "address_months": 10,
                   "dti": 20, "income": 4, "revolving_utilisation": 0})


def test_reasons_largest_shortfall_first():
    assert engine.reasons_for(SHORT, no_file=False) == (
        "bureau_score", "dti", "address_months", "enquiries_6m")
    assert engine.reasons_for(SHORT, no_file=False, k=2) == (
        "bureau_score", "dti")


def test_no_file_is_said_once():
    got = engine.reasons_for(SHORT, no_file=True)
    assert got[0] == "no_file"
    assert not {"bureau_score", "dti", "enquiries_6m"} & set(got)
    assert "address_months" in got


def test_steps_in_order():
    d = engine._decide("A1", "public_record", 600, "approve", SHORT,
                       False, 1_000_000, 0.2, 0.5)
    assert (d.decision, d.stage, d.reasons) == ("decline", "policy",
                                                ("public_record",))
    assert d.amount_cents == 0
    d = engine._decide("A1", None, 540, "decline", SHORT, False,
                       1_000_000, 0.2, 0.5)
    assert d.decision == "decline" and d.reasons[0] == "bureau_score"
    d = engine._decide("A1", None, 552, "refer", SHORT, False,
                       1_000_000, 0.47, 0.5)
    assert d.decision == "refer" and d.amount_cents == 800_000
    assert len(d.reasons) == 4
    d = engine._decide("A1", None, 600, "approve", SHORT, False,
                       1_000_000, 0.2, 0.5)
    assert d.decision == "approve" and d.reasons == ()
    assert d.amount_cents == 1_000_000


def test_reason_text_and_actionable():
    assert engine.reason_text(("no_file", "public_record")) == [
        "no credit history at the bureau", "public record"]
    assert engine.actionable("bureau_score")
    assert not engine.actionable("oldest_account_months")


def test_engine_never_reads_the_truth():
    for mod in (engine, pol):
        src = inspect.getsource(mod)
        assert "truth=True" not in src and "truth.duckdb" not in src


@pytest.fixture(scope="module")
def apps_2025():
    if not LOANBOOK.exists() or not (reject.REJECT /
                                     "mark2_retro_ws.json").exists():
        pytest.skip("no loan book or no saved Mark II-R")
    from ballast import data
    raw = data.load_applications(unknowns=False)
    return raw[raw["product"].astype(str).eq("personal")
               & (raw["app_date"].astype(str) >= "2025-06-01")
               & (raw["app_date"].astype(str) < "2025-07-01")]


def test_decide_all_follows_the_policy(apps_2025):
    card = engine.load_champion(POLICY)
    d = engine.decide_all(apps_2025, POLICY, card)
    assert len(d) == len(apps_2025)
    rule = pol.policy_reason(apps_2025)
    assert (d["stage"].eq("policy") == rule.notna()).all()
    scored = d[d["stage"] == "score"]
    assert (scored["decision"] == POLICY.zone(scored["score"])).all()
    assert (d.loc[d["decision"] == "decline", "amount_cents"] == 0).all()
    assert (d.loc[d["decision"] == "approve", "reasons"]
            .map(len) == 0).all()
    again = engine.decide_all(apps_2025, POLICY, card)
    pd.testing.assert_frame_equal(d, again)


def test_one_application_decides_as_the_frame_does(apps_2025):
    card = engine.load_champion(POLICY)
    d = engine.decide_all(apps_2025, POLICY, card)
    for i in apps_2025.index[:25]:
        one = engine.decide(apps_2025.loc[[i]], POLICY, card)
        row = d.loc[i]
        assert (one.decision, one.score, one.reasons) == (
            row["decision"], row["score"], row["reasons"])
    with pytest.raises(ValueError):
        engine.decide(apps_2025.iloc[:2], POLICY, card)


def test_other_products_are_refused(apps_2025):
    card = engine.load_champion(POLICY)
    wrong = apps_2025.iloc[:1].copy()
    wrong["product"] = "card"
    with pytest.raises(ValueError):
        engine.decide_all(wrong, POLICY, card)
