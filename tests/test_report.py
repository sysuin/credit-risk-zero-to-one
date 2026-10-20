"""Tests for ballast.report: the risk committee pack's layout, and the
pack written from Fernhill's saved results."""
from __future__ import annotations

from pathlib import Path

import pytest

from ballast import appetite as ap
from ballast import report
from ballast.config import BALLAST

needs_saved = pytest.mark.skipif(
    not (BALLAST / "appetite" / "plan_2025-12-31.json").exists(),
    reason="no saved statement and plan")


def test_paragraphs_and_items_fit_the_page():
    long = "word " * 80
    for line in report.para(long, "- ") + report.item(12, long):
        assert len(line) <= report.WIDTH
    lines = report.item(3, long)
    assert lines[0].startswith("3. ")
    assert all(s.startswith("   ") for s in lines[1:])


def test_block_is_fenced_and_stripped():
    out = report.block(["a  ", "b"])
    assert out == ["```", "a", "b", "```"]


def test_money():
    assert report.money(54_310_000_000) == "$543.1m"


def test_module_never_reads_the_truth():
    src = Path(report.__file__).read_text()
    assert "truth=" not in src and "TRUTH" not in src


@needs_saved
def test_pack_from_the_saved_results():
    a = ap.load()
    text = report.pack(a)
    lines = text.splitlines()
    assert max(len(s) for s in lines) <= report.WIDTH
    heads = [s for s in lines if s.startswith("## ")]
    assert [h.split(" ", 2)[2] for h in heads] == [
        "Headline", "Risk appetite dashboard", "Provisions",
        "Capital and stress", "Concentrations", "Monitoring alerts",
        "Model risk", "The commercial plan, measured",
        "Decisions requested"]
    assert text.count("```") % 2 == 0
    for m in ap.METRICS:
        assert any(s.startswith(m[0] + " ") for s in lines)
    assert len(report.decisions(a)) == 8
    assert report.pack(a) == text                 # it repeats
