"""Tests for ballast.validation: stability, the PD tests and the
traffic light, the year-by-year backtest's refits, and the reports
and the rule that concludes them."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import binom

from ballast import governance as gv
from ballast import validation as vd
from ballast.config import ROOT


def test_psi_is_zero_for_the_same_population_and_grows_with_a_shift():
    rng = np.random.default_rng(1)
    x = rng.normal(570, 25, 20_000)
    edges = np.quantile(x, np.arange(0.1, 1.0, 0.1))
    assert vd.psi(x, x, edges) == pytest.approx(0.0)
    small = vd.psi(x, x + 5, edges)
    large = vd.psi(x, x + 25, edges)
    assert 0 < small < large
    assert vd.psi_reading(small) == "stable"
    assert vd.psi_reading(large) == "act"
    assert vd.shares(x, edges).sum() == pytest.approx(1.0)


def test_psi_floors_an_empty_band():
    edges = [1, 2, 3]
    assert np.isfinite(vd.psi([0, 0, 1, 2], [3, 3, 3, 3], edges))


def test_binomial_and_jeffreys_agree_in_direction():
    n, pd_ = 1_000, 0.02
    assert vd.binomial_p(n, 0, pd_) == pytest.approx(1.0)
    assert vd.binomial_p(n, 30, pd_) == pytest.approx(binom.sf(29, n, pd_))
    ps = [vd.jeffreys_p(n, d, pd_) for d in (5, 20, 40)]
    assert ps[0] > ps[1] > ps[2]
    assert vd.binomial_p(n, 40, pd_) < 0.001
    assert vd.binomial_low_p(n, 5, pd_) < 0.01
    lo, hi = vd.jeffreys_interval(n, 20)
    assert lo < 0.02 < hi


def test_traffic_light_and_correlation():
    n, pd_ = 5_000, 0.03
    assert vd.traffic_light(n, 150, pd_) == "green"
    amber, red = vd.limits(n, pd_)
    assert amber < red
    assert vd.traffic_light(n, int(amber) + 1, pd_) == "amber"
    assert vd.traffic_light(n, int(red) + 1, pd_) == "red"
    assert vd.traffic_light(n, 10, pd_) == "green"   # too few: not lit
    # correlated defaults widen the range: red becomes green
    assert vd.traffic_light(n, int(red) + 1, pd_, rho=0.1) == "green"
    assert vd.vasicek_quantile(pd_, 0.1, 0.5) < pd_ < \
        vd.vasicek_quantile(pd_, 0.1, 0.95)


def test_detectable_error_shrinks_with_the_sample():
    a, b = vd.detectable(1_000, 0.03), vd.detectable(20_000, 0.03)
    assert a > b > 1.0


def test_backtest_never_fits_on_the_year_it_scores(monkeypatch):
    from ballast.parameters import pd as pdm
    rng = np.random.default_rng(2)
    months = pd.date_range("2016-03-31", "2021-12-31", freq="QE")
    rows = []
    for i in range(400):
        for m in months:
            age = (m.year - 2016) * 12 + m.month + 3 * (i % 20)
            missed = int(rng.choice(3, p=[0.9, 0.07, 0.03]))
            rows.append((f"PL{i:07d}", m, age, missed, 560 + i % 60,
                         5.0 + rng.random()))
    p = pd.DataFrame(rows, columns=["account_id", "month", "mob",
                                    "missed", "score", "u_ahead"])
    p["y"] = (rng.random(len(p)) < 0.04).astype(int)
    p["complete"] = p["month"] <= pd.Timestamp("2020-12-31")
    seen = []
    real = pdm.fit_pd_model

    def spy(panel, macro=True):
        seen.append(set(panel["month"].dt.year))
        return real(panel, macro)

    monkeypatch.setattr(pdm, "fit_pd_model", spy)
    out = vd.pd_backtest(p, [2020, 2021], 5.0)
    assert {2019, 2020}.isdisjoint(seen[0])
    assert {2020, 2021}.isdisjoint(seen[1])
    assert set(out["month"]) == {pd.Timestamp("2019-12-31"),
                                 pd.Timestamp("2020-12-31")}
    assert out["pit"].between(0, 1).all() and out["ttc"].notna().all()


def test_conclusion_follows_the_findings():
    low = vd.Finding("X-1", "low", "a record", "fix it")
    med = vd.Finding("X-2", "medium", "a weakness", "watch it")
    block = vd.Finding("X-3", "high", "cannot rebuild", "replace",
                       blocks=True)
    assert vd.conclude([]) == "approved"
    assert vd.conclude([low]) == "approved"
    assert vd.conclude([low, med]) == "approved with conditions"
    assert vd.conclude([med, block]) == "not approved"


def test_reports_name_register_models_and_fit_the_page():
    ids = {e["id"] for e in gv.REGISTER}
    seen = set()
    for key, r in vd.REPORTS.items():
        assert key == r.model and r.model in ids
        assert vd.conclude(r.findings) in vd.CONCLUSIONS
        assert r.scope and r.findings
        for f in r.findings:
            assert f.severity in vd.SEVERITY and f.id not in seen
            assert f.id.startswith(r.model + "-")
            seen.add(f.id)
        assert all(len(x) <= vd.WIDTH for x in vd.render(r))
    assert all(len(x) <= vd.WIDTH
               for x in vd.summary_lines(vd.REPORTS.values()))


def test_save_and_read_back(tmp_path):
    files = vd.save(vd.REPORTS.values(), path=tmp_path)
    assert files[0].name == "reports.json"
    back = vd.load(tmp_path)
    assert [r["model"] for r in back] == list(vd.REPORTS)
    e = vd.register_entries(tmp_path)
    assert e["FRM"]["conclusion"] == "not approved"
    assert e["MK2R"]["validated"] == str(vd.VALIDATION_DATE.year)


def test_validation_never_reads_the_truth():
    src = (ROOT / "code" / "ballast" / "validation.py").read_text()
    assert "truth=True" not in src and "truth.duckdb" not in src
