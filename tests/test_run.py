"""Ballast v1.0's single command: the steps, the reconciliation rule,
and a check-only run over the saved results (fast; no reruns)."""
from __future__ import annotations

import pytest

from ballast import run
from ballast.config import BALLAST, LOANBOOK, ROOT

SAVED = [BALLAST / "ecl", BALLAST / "capital", BALLAST / "stress",
         BALLAST / "portfolio", BALLAST / "appetite", BALLAST / "report"]
needs_saved = pytest.mark.skipif(
    not LOANBOOK.exists() or not all(p.exists() for p in SAVED),
    reason="needs the loan book and the saved results of Chapters 20-29")


def test_steps_in_the_book_order_with_a_mode_each():
    names = [s[0] for s in run.STEPS]
    assert names[0] == "data" and names[-1] == "pack"
    assert names.index("provision") < names.index("capital") \
        < names.index("stress") < names.index("appetite")
    assert {s[2] for s in run.STEPS} == {"rerun", "saved"}
    saved = {s[0] for s in run.STEPS if s[2] == "saved"}
    assert saved == {"parameters", "portfolio", "validation"}


def test_a_figure_equals_only_what_its_chapter_printed():
    src = "code/01/02_charge_offs.out"
    assert run.Check("x", "1,706,057", "1,706,057", src, 1).equal
    assert not run.Check("x", "1,706,058", "1,706,057", src, 1).equal
    # equal strings are not enough if the chapter no longer prints it
    assert not run.Check("x", "9,999,999", "9,999,999", src, 1).equal
    assert run.Check("x", "6", "6", "code/29/12_examination.out", 29,
                     context="{} alerts for attention").equal


def test_a_rerun_equals_its_file_only_when_the_same():
    assert run.Check("x", "$1", "", "file", 0, same=True).equal
    assert not run.Check("x", "$1", "", "file", 0, same=False).equal
    assert run.same_cents(100.0, 100.4)
    assert not run.same_cents(100.0, 101.0)


def test_one_difference_fails_the_run():
    def fine(ctx, rerun):
        return [run.Check("a", "1", "", "f", 0, same=True)]

    def broken(ctx, rerun):
        return [run.Check("b", "2", "", "f", 0, same=False)]

    rep = run.run(con=object(), steps=[("one", "1", "rerun", fine),
                                       ("two", "2", "saved", broken)])
    assert not rep.ok and rep.steps[0].ok and not rep.steps[1].ok
    assert "1 DIFFER" in rep.summary()[1]
    assert all(len(x) <= run.WIDTH for x in rep.table())


@needs_saved
def test_check_only_run_reconciles_every_figure():
    rep = run.run(rerun=False)
    bad = [c.label for c in rep.checks if not c.equal]
    assert not bad, bad
    assert len(rep.checks) >= 30
    assert all(len(x) <= run.WIDTH for x in rep.table())
    assert {s.mode for s in rep.steps} == {"check"}


def test_makefile_has_the_run_target():
    text = (ROOT / "Makefile").read_text()
    assert "\nrun:" in text and "-m ballast.run" in text
    assert "\ntest:" in text and "\nverify:" in text     # kept


def test_run_never_reads_the_truth():
    src = (ROOT / "code" / "ballast" / "run.py").read_text()
    assert "truth=True" not in src and "TRUTH" not in src
