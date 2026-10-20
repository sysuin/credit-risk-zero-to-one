"""Tests for ballast.governance: the tiering rule and its inheritance,
the register and its width, the findings log, who answers for what,
the lending authority matrix and the override helpers."""
from __future__ import annotations

import json

import pandas as pd
import pytest

import fernhill
from ballast import governance as gv
from ballast.config import BALLAST, LOANBOOK, ROOT

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")
needs_ecl = pytest.mark.skipif(
    not (BALLAST / "ecl").exists(), reason="no saved provision")


def test_materiality_follows_use_then_money():
    assert gv.materiality_level("external", None) == "high"
    assert gv.materiality_level("decide", 10) == "medium"
    assert gv.materiality_level("decide",
                                gv.HIGH_DECIDED_CENTS) == "high"
    assert gv.materiality_level("inform", 10 ** 15) == "low"


def test_doubt_raises_one_tier_and_no_further():
    assert gv.own_tier("low", False) == 3
    assert gv.own_tier("low", True) == 2
    assert gv.own_tier("medium", True) == 1
    assert gv.own_tier("high", True) == 1
    assert gv.elevated(None, "")
    assert gv.elevated(gv.THIN_EVIDENCE - 1, "")
    assert not gv.elevated(gv.THIN_EVIDENCE, "")
    assert gv.elevated(10_000, "an untestable assumption")


def test_inherit_takes_the_highest_tier_downstream():
    own = {"a": 3, "b": 2, "c": 1, "d": 3, "x": None}
    inputs = {"a": [], "b": ["a"], "c": ["b"], "d": [], "x": ["d"]}
    t = gv.inherit(own, inputs)
    assert t == {"a": 1, "b": 1, "c": 1, "d": 3, "x": None}


def test_inherit_survives_a_cycle():
    t = gv.inherit({"a": 3, "b": 1}, {"a": ["b"], "b": ["a"]})
    assert t == {"a": 1, "b": 1}


def test_register_entries_are_complete_and_inputs_exist():
    ids = [r["id"] for r in gv.REGISTER]
    assert len(ids) == len(set(ids))
    for r in gv.REGISTER:
        assert r["use"] in gv.LEVEL
        assert r["owner"] in gv.OWNER_SHORT
        assert set(r["inputs"]) <= set(ids)
        assert len(r["name"]) <= 25
        assert r["not_for"]


def test_findings_are_well_formed_and_fit_the_page():
    ids = {r["id"] for r in gv.REGISTER}
    for f in gv.FINDINGS:
        assert f["model"] in ids
        assert f["severity"] in gv.SEVERITY
        assert f["status"] in gv.STATUS
        assert len(f["issue"]) <= 36
    t = gv.findings_table()
    assert t.to_numpy().sum() == len(gv.FINDINGS)


def test_one_role_answers_for_each_task():
    for codes in gv.RACI.values():
        c = codes.split()
        assert len(c) == len(gv.ROLES)
        assert c.count("A") == 1
    assert all(len(ln) <= 68 for ln in gv.raci_lines())


def test_round_down():
    assert gv.round_down(1_500_000_000) == 1_000_000_000
    assert gv.round_down(4_000) == 2_500
    assert gv.round_down(7_600) == 7_500
    assert gv.round_down(0) == 0


def test_authority_shrinks_with_grade_and_grows_with_level():
    m = gv.authority_matrix()
    for lv in m.index:
        row = m.loc[lv].to_numpy()
        assert all(row[i] >= row[i + 1] for i in range(len(row) - 1))
    for g in m.columns:
        col = m[g].to_numpy()
        assert all(col[i] <= col[i + 1] for i in range(len(col) - 1))
    assert (m.to_numpy() == 0).sum() > 0     # some grades need more


def test_approver_boundaries():
    lim = gv.authority_limit(1, 3)
    assert gv.approver(lim, 3) in gv.LEVELS[:2]
    assert gv.approver(lim + 1, 3) == "credit committee"
    assert gv.approver(10 ** 12, 1) == gv.BOARD
    assert gv.approver(1, 10) == "credit committee"


def test_depth_band_and_binomial_z():
    b = gv.depth_band(pd.Series([-5, -11, -40, -41, -80, -81, -200]))
    assert list(b) == ["in the refer band", "11-40 below", "11-40 below",
                       "41-80 below", "41-80 below", "over 80 below",
                       "over 80 below"]
    assert gv.binomial_z(50, 100, 0.5) == 0
    assert gv.binomial_z(60, 100, 0.5) == pytest.approx(2.0)


@needs_book
@needs_ecl
def test_inventory_from_the_book():
    con = fernhill.connect()
    inv = gv.build_inventory(con)
    by = {e["id"]: e for e in inv}
    assert by["MK2"]["tier"] is None
    assert by["MK2R"]["own_tier"] == 2 and by["MK2R"]["tier"] == 1
    assert by["ECL"]["materiality_cents"] > by["PD12"]["materiality_cents"]
    assert all(len(ln) <= 68 for ln in gv.register_lines(inv))
    json.dumps(inv)                         # saveable as it stands
    checks = gv.check_artefacts(inv, ROOT)
    assert {c["id"] for c in checks} == set(by)


@needs_book
@needs_ecl
def test_saved_validations_reach_the_register():
    done = gv.validations()
    if not done:
        pytest.skip("no saved validation reports")
    inv = {e["id"]: e for e in gv.build_inventory(fernhill.connect())}
    for k, v in done.items():
        assert inv[k]["validated"] == v["validated"]
        assert inv[k]["conclusion"] == v["conclusion"]
        if v["conclusion"] == "not approved":
            assert inv[k]["due"] == "blocked"
    ids = {f["id"] for f in gv.new_from_validation()}
    assert not ids & set(gv.SAME_AS.values())


@needs_book
def test_document_names_every_section():
    con = fernhill.connect()
    inv = gv.build_inventory(con)
    text, state = gv.document("MK2R", inv)
    assert set(state) == {t for t, _ in gv.DOC_TEMPLATE}
    assert state["Performance"] == "empty"
    for title, _ in gv.DOC_TEMPLATE:
        assert f"## {title}" in text
    with pytest.raises(NotImplementedError):
        gv.document("MK1", inv)


def test_governance_never_reads_the_truth():
    src = (ROOT / "code" / "ballast" / "governance.py").read_text()
    assert "truth=True" not in src and "TRUTH" not in src
