"""Tests for ballast.appetite: the status rule, the capital target, the
allocation of economic capital, returns and margins, the reshaped
stress book and the plan's steps, and the statement on Fernhill's
saved results at 31 December 2025."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import fernhill
from ballast import appetite as ap
from ballast.config import BALLAST, LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")
needs_saved = pytest.mark.skipif(
    not (BALLAST / "appetite" / "limits_2025-12-31.json").exists(),
    reason="no saved watchlist limits")


def test_rag_both_directions():
    assert ap.rag(0.17, 0.16, 0.115) == "green"
    assert ap.rag(0.16, 0.16, 0.115) == "green"
    assert ap.rag(0.12, 0.16, 0.115) == "amber"
    assert ap.rag(0.10, 0.16, 0.115) == "red"
    assert ap.rag(0.05, 0.10, 0.15, higher=False) == "green"
    assert ap.rag(0.12, 0.10, 0.15, higher=False) == "amber"
    assert ap.rag(0.18, 0.10, 0.15, higher=False) == "red"


def test_capital_target_arithmetic():
    cap = {"requirement": 0.08, "minimum": 0.045}
    summ = {"year_zero": {"cet1_sa": 0.167},
            "trough_sa": {"base": 0.157, "severe": 0.097,
                          "stress_2026": -0.021}}
    t = ap.capital_target(cap, summ, buffer=0.01)
    assert t["drop"]["severe"] == pytest.approx(0.070)
    assert t["need"]["stress_2026"] == pytest.approx(0.268)
    assert t["target"] == pytest.approx(0.160)
    assert t["tolerance"] == pytest.approx(0.115)
    # the target is rounded up, never down
    t2 = ap.capital_target(cap, dict(summ, trough_sa=dict(
        summ["trough_sa"], severe=0.0965)), buffer=0.01)
    assert t2["target"] == pytest.approx(0.161)


def test_ec_ceiling_leaves_the_minimum():
    cap = {"cet1": 1000.0, "minimum": 0.045, "sa_rwa": 6000.0}
    c = ap.ec_ceiling(cap)
    assert cap["cet1"] - c * cap["cet1"] == pytest.approx(270.0)


def test_allocation_adds_up_to_economic_capital():
    c = pd.DataFrame({"kind": ["pool", "name", "name"],
                      "id": ["p", "a", "b"], "segment": ["x", "c", "c"],
                      "ead": [10.0, 20.0, 30.0], "el": [1.0, 2.0, 3.0],
                      "es_999": [3.0, 12.0, 30.0]})
    out = ap.allocate(c, 26.0)
    assert out.ec.sum() == pytest.approx(26.0)
    assert out.ec.iloc[2] / out.ec.iloc[1] == pytest.approx(27 / 10)


def test_band_of():
    assert list(ap.band_of([1, 5, 6, 8, 9, 10])) == [
        "grades 1-5", "grades 1-5", "grades 6-8", "grades 6-8",
        "grades 9-10", "grades 9-10"]


def test_company_ead_uses_the_headroom_on_revolvers_only():
    cb = pd.DataFrame({"company_id": ["A", "A", "B"],
                       "kind": ["revolver", "term", "revolver"],
                       "balance_cents": [100, 50, 80],
                       "limit_cents": [200, 400, 60]})
    e = ap.company_ead(cb, ccf=0.5)
    assert e["A"] == pytest.approx(100 + 50 + 50)
    assert e["B"] == pytest.approx(80)        # over its limit: no head


def _inputs():
    cb = pd.DataFrame({
        "account_id": ["C0001-F1", "C0002-F1", "C0003-F1"],
        "company_id": ["C0001", "C0002", "C0003"],
        "kind": ["revolver", "term", "revolver"],
        "balance_cents": [100, 200, 50], "limit_cents": [300, 200, 50],
        "rate_pct": [6.0, 6.5, 7.0], "grade": [9, 3, 10],
        "remaining": [6, 40, 30]})
    cap = pd.DataFrame({
        "account_id": cb.account_id, "segment": "commercial",
        "product": ["commercial_revolver", "commercial_term",
                    "commercial_revolver"],
        "drawn_cents": cb.balance_cents, "limit_cents": cb.limit_cents,
        "undrawn_cents": [200, 0, 0], "sa_ccf": [0.4, 0.0, 0.4],
        "sa_ead": [180.0, 200.0, 50.0], "sa_rw": [1.0, 1.0, 1.0],
        "sa_rwa": [180.0, 200.0, 50.0]})
    return {"cb": cb, "book": cb.copy(), "capital": cap}


def test_reshape_scales_drawn_headroom_and_margin(monkeypatch):
    monkeypatch.setattr(ap.stress, "provision",
                        lambda inp, at: {"total": 0.0})
    inp = _inputs()
    same = ap.reshape(inp)
    pd.testing.assert_frame_equal(same["cb"], inp["cb"])
    new = ap.reshape(inp, drawn=pd.Series({"C0001-F1": 0.5}),
                     headroom=pd.Series({"C0003-F1": 0.0}),
                     margin_bps=pd.Series({"C0002-F1": 100.0}))
    cb = new["cb"].set_index("account_id")
    assert cb.loc["C0001-F1", "balance_cents"] == 50
    assert cb.loc["C0001-F1", "limit_cents"] == 150
    assert cb.loc["C0002-F1", "rate_pct"] == pytest.approx(7.5)
    cap = new["capital"].set_index("account_id")
    assert cap.loc["C0001-F1", "sa_ead"] == pytest.approx(50 + 0.4 * 100)
    assert cap.loc["C0001-F1", "sa_rwa"] == pytest.approx(90.0)
    # the source frames are untouched
    assert inp["cb"].balance_cents.iloc[0] == 100


def test_plan_steps_are_cumulative():
    inp = _inputs()
    steps = ap.plan_steps(inp, tier1=1500.0, gap_bps={3: 50.0},
                          watch_limit=10.0)
    labels = [s[0] for s in steps]
    assert len(steps) == 5 and labels[0].startswith("watchlist")
    head = steps[0][2]
    assert list(head.index) == ["C0001-F1", "C0003-F1"]
    gone = steps[1][1]
    assert list(gone.index) == ["C0001-F1"]         # matures in 6 months
    # 10% of Tier 1 is 150: client C0002 (200) is cut to three-quarters
    assert steps[2][1]["C0002-F1"] == pytest.approx(0.75)
    assert steps[3][3]["C0002-F1"] == 50.0
    # the rest of the watchlist (C0003, EAD 50) is run down to 10
    assert steps[4][1]["C0003-F1"] == pytest.approx(0.2)


def test_statement_covers_every_metric():
    ids = [m[0] for m in ap.METRICS]
    assert len(ids) == len(set(ids)) == 14
    areas = {m[1] for m in ap.METRICS}
    assert areas == {"capital", "earnings", "quality", "concentration",
                     "models"}
    pos = {"values": {i: 1.0 for i in ids},
           "thresholds": {i: (0.5, 2.0) for i in ids}}
    st = ap.statement(pos)
    assert set(st.status) <= {"green", "amber", "red"}
    assert (st.id == ids).all()


def test_fmt():
    assert ap.fmt(0.1665, "pct") == "16.7%"
    assert ap.fmt(107_890_000_000, "usd") == "$1,079m"
    assert ap.fmt(8.0, "n") == "8"


def test_module_never_reads_the_truth():
    src = Path(ap.__file__).read_text()
    assert "truth=" not in src and "TRUTH" not in src


@needs_book
@needs_saved
def test_position_on_the_saved_results():
    con = fernhill.connect()
    pos = ap.position(con)
    v, th = pos["values"], pos["thresholds"]
    assert v["C1"] == pytest.approx(0.1665, abs=5e-4)
    assert th["C1"] == pytest.approx((0.160, 0.115))
    assert v["C2"] < 0                            # the supervisor's test
    assert v["N1"] == pytest.approx(0.180, abs=5e-4)
    t = pos["returns"]
    # returns are before costs: the commercial book loses money on
    # its capital, retail earns well above the hurdle
    com = ap.total(t, [i for i in t.index if i not in ap.RETAIL])
    ret = ap.total(t, [i for i in t.index if i in ap.RETAIL])
    assert com.roc < 0 < ap.HURDLE < ret.roc
    assert t.ec.sum() == pytest.approx(ap.pf.load()["ec_999"])
    assert pos["model_risk"]["unvalidated"]
    st = ap.statement(pos)
    assert (st.status == "red").sum() >= 1
