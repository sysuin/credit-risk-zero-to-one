"""Validation: the tests an independent validator runs on a credit
model, and the reports that record what they found.

The tests are the ones a validator reaches for whatever the model:
population stability, binomial and Jeffreys tests of a PD against the
defaults that followed, a traffic light for a run of years (with and
without the correlation that makes defaults arrive together), and the
power of a test to see an error at all. The reports are records: what
was validated, when, by whom, on what scope, what was found and how
serious it is, and the conclusion that follows from the findings by a
stated rule.

    from ballast import validation as vd
    vd.psi(expected_scores, actual_scores, edges)
    vd.binomial_p(n, d, pd); vd.jeffreys_p(n, d, pd)
    vd.traffic_light(n, d, pd)                 # green, amber or red
    vd.traffic_light(n, d, pd, rho=0.08)       # defaults correlated
    vd.detectable(n, pd)                       # the smallest error seen
    r = vd.REPORTS["MK2R"]; vd.conclude(r.findings)
    vd.render(r, measures)                     # the report, 68 wide
    vd.save(vd.REPORTS.values())    # data/ballast/validation/

Ballast never reads the truth here: a validator works on what the
bank can see.
"""
from __future__ import annotations

import datetime as dt
import json
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta, binom, norm

from ballast.config import AS_OF, BALLAST

OUT = BALLAST / "validation"
WIDTH = 68                       # a report line, as printed

# ------------------------------------------------ population stability
# Fernhill's reading of a PSI, the conventional one: under 0.10 the
# population has not moved enough to matter; 0.10 to 0.25 it has moved
# and the reason must be found; over 0.25 the model is being used on a
# population it was not built on.
PSI_WATCH, PSI_ACT = 0.10, 0.25


def shares(x, edges) -> np.ndarray:
    """The share of `x` in each band cut at `edges` (left-closed),
    with a band below the first edge and one above the last."""
    i = np.searchsorted(np.asarray(edges, float),
                        np.asarray(x, float), side="right")
    return np.bincount(i, minlength=len(edges) + 1) / len(i)


def psi(expected, actual, edges, floor: float = 1e-4) -> float:
    """Population stability index between two samples of a score (or
    any characteristic): the sum over bands of (a - e) ln(a / e).
    Empty bands are floored so that the logarithm exists."""
    e = np.maximum(shares(expected, edges), floor)
    a = np.maximum(shares(actual, edges), floor)
    return float(((a - e) * np.log(a / e)).sum())


def psi_reading(value: float) -> str:
    return ("stable" if value < PSI_WATCH else
            "investigate" if value < PSI_ACT else "act")


# ------------------------------------------------------ PD backtests

def binomial_p(n: int, d: int, pd_: float) -> float:
    """One-sided binomial test that the PD is not too low: the chance
    of `d` or more defaults among `n` borrowers who each default with
    probability `pd_`, independently. Small means the PD is light."""
    if n == 0:
        return float("nan")
    return float(binom.sf(d - 1, n, pd_))


def binomial_low_p(n: int, d: int, pd_: float) -> float:
    """The other tail: the chance of `d` or fewer defaults. Small
    means the PD is heavy (cautious)."""
    if n == 0:
        return float("nan")
    return float(binom.cdf(d, n, pd_))


def jeffreys_p(n: int, d: int, pd_: float) -> float:
    """Jeffreys test that the PD is not too low: the probability,
    under a Jeffreys prior Beta(1/2, 1/2) updated with `d` defaults in
    `n`, that the true default rate is at or below `pd_`. Small means
    the evidence puts the true rate above the PD."""
    if n == 0:
        return float("nan")
    return float(beta.cdf(pd_, d + 0.5, n - d + 0.5))


def jeffreys_interval(n: int, d: int, level: float = 0.95
                      ) -> tuple[float, float]:
    """The central Jeffreys interval for a default rate."""
    a = (1 - level) / 2
    return (float(beta.ppf(a, d + 0.5, n - d + 0.5)),
            float(beta.ppf(1 - a, d + 0.5, n - d + 0.5)))


# Fernhill's traffic light for a PD's yearly backtest: green while the
# defaults seen sit inside the 95% range the PD implies, amber to
# 99.9%, red beyond. The levels are a convention, chosen in advance.
AMBER, RED = 0.95, 0.999


def vasicek_quantile(pd_: float, rho: float, q: float) -> float:
    """The default rate that a one-factor model with asset correlation
    `rho` exceeds with probability 1 - q, for a large book."""
    return float(norm.cdf((norm.ppf(pd_) + np.sqrt(rho) * norm.ppf(q))
                          / np.sqrt(1 - rho)))


def limits(n: int, pd_: float, rho: float = 0.0
           ) -> tuple[float, float]:
    """The default counts at which the light turns amber and red:
    binomial when defaults are independent, the one-factor model's
    quantiles (times n) when they are correlated."""
    if rho == 0.0:
        return (float(binom.ppf(AMBER, n, pd_)),
                float(binom.ppf(RED, n, pd_)))
    return (n * vasicek_quantile(pd_, rho, AMBER),
            n * vasicek_quantile(pd_, rho, RED))


def traffic_light(n: int, d: int, pd_: float, rho: float = 0.0) -> str:
    """Green, amber or red for `d` defaults seen among `n` borrowers
    whose average PD was `pd_`. Only too many defaults change the
    colour: a PD that is too cautious is reported, not lit."""
    amber, red = limits(n, pd_, rho)
    return "red" if d > red else "amber" if d > amber else "green"


def detectable(n: int, pd_: float, power: float = 0.8,
               level: float = AMBER) -> float:
    """The smallest true default rate, as a multiple of `pd_`, that a
    one-sided binomial test at `level` would flag with chance
    `power`: how wrong a PD must be before a year's backtest can see
    it."""
    crit = binom.ppf(level, n, pd_)
    lo, hi = pd_, min(1.0, 20 * pd_)
    for _ in range(60):
        mid = (lo + hi) / 2
        if binom.sf(crit, n, mid) >= power:
            hi = mid
        else:
            lo = mid
    return hi / pd_


def pd_backtest(panel: pd.DataFrame, years, long_run_u: float,
                u: pd.Series | None = None) -> pd.DataFrame:
    """Chapter 18's 12-month model backtested year by year. For each
    year Y, the model is refitted without any quarter end whose twelve
    months overlap Y (those of Y - 1 and Y), so the year is scored by
    a model that never saw its defaults, and it scores the loans open
    on 31 December of Y - 1. `pit` reads the unemployment the year
    brought, `ttc` the long-run average and, given the monthly
    unemployment `u`, `flat` the rate on the day held for the year (a
    forecast of no change); `y` is a default during Y."""
    from ballast.parameters import pd as pdm
    out = []
    known = panel[panel["complete"]]
    for y in years:
        start = pd.Timestamp(y - 1, 12, 31)
        seen = known["month"].dt.year.isin([y - 1, y])
        model = pdm.fit_pd_model(known[~seen])
        rows = panel[panel["month"] == start].copy()
        rows["year"] = y
        rows["pit"] = model.pd(rows).to_numpy()
        rows["ttc"] = model.pd(rows, u_ahead=long_run_u).to_numpy()
        if u is not None:
            rows["flat"] = model.pd(rows, u_ahead=float(u[start])
                                    ).to_numpy()
        out.append(rows)
    return pd.concat(out, ignore_index=True)


def migration_share(grade_a, grade_b) -> float:
    """The share of borrowers whose grade differs between two dates."""
    a, b = np.asarray(grade_a), np.asarray(grade_b)
    return float((a != b).mean())


# ---------------------------------------------------------- reporting
# Severity is Fernhill's (Chapter 29's log uses the same three):
# high = could materially misstate a decision, a price, the provision
# or capital, or treat customers unfairly; medium = weakens the model
# in a known part of the book or rests on evidence too thin to
# confirm; low = records and housekeeping.
SEVERITY = ("high", "medium", "low")
CONCLUSIONS = ("approved", "approved with conditions", "not approved")
VALIDATION_DATE = dt.date(2026, 2, 6)     # the reports' date
VALIDATOR = "model validation (second line)"


@dataclass
class Finding:
    """One weakness: what it is, how serious, and what must happen.
    `blocks` says the model may not be used as it stands until the
    action is done."""
    id: str
    severity: str
    issue: str
    action: str
    section: str = ""
    blocks: bool = False


@dataclass
class Report:
    model: str                    # the register's id (Chapter 29)
    name: str
    scope: list[str]
    findings: list[Finding] = field(default_factory=list)
    date: dt.date = VALIDATION_DATE
    data_to: dt.date = AS_OF
    validator: str = VALIDATOR
    use: str = ""                 # what it is approved for
    confirmed: list[str] = field(default_factory=list)


def conclude(findings: list[Finding]) -> str:
    """Fernhill's rule: any finding that blocks use, not approved; any
    high or medium finding, approved with conditions (its actions are
    the conditions); otherwise approved."""
    if any(f.blocks for f in findings):
        return "not approved"
    if any(f.severity in ("high", "medium") for f in findings):
        return "approved with conditions"
    return "approved"


def wrap(text: str, indent: str = "", hang: str | None = None,
         width: int = WIDTH) -> list[str]:
    """Text wrapped to `width`, the first line after `indent` and the
    rest after `hang` (as wide as `indent` unless given)."""
    hang = " " * len(indent) if hang is None else hang
    return textwrap.wrap(text, width=width, initial_indent=indent,
                         subsequent_indent=hang) or [indent]


def render(r: Report, measures: dict[str, str] | None = None
           ) -> list[str]:
    """The report as printed and saved: every line at most WIDTH."""
    out = [f"VALIDATION REPORT  {r.model}  {r.name}", "=" * WIDTH]
    out += wrap(f"Date {r.date.day} {r.date:%B %Y}; data to "
                f"{r.data_to.day} {r.data_to:%B %Y}; by {r.validator}.")
    out += ["", "Scope"] + [x for s in r.scope for x in wrap(s, "  - ")]
    if measures:
        out += ["", "Key measures"]
        for k, v in measures.items():
            out += wrap(f"{k}: {v}", "  ")
    if r.confirmed:
        out += ["", "Confirmed"]
        out += [x for c in r.confirmed for x in wrap(c, "  - ")]
    out += ["", "Findings"]
    for f in r.findings:
        tag = f"{f.severity}, blocks use" if f.blocks else f.severity
        out.append(f"  {f.id} ({tag}, section {f.section})")
        out += wrap(f.issue, "    ")
        out += wrap(f"Action: {f.action}", "    ", " " * 12)
    out += ["", f"Conclusion: {conclude(r.findings).upper()}"]
    if r.use:
        out += wrap(f"For: {r.use}", "  ", "       ")
    return out


def summary_lines(reports) -> list[str]:
    """One line per model: its findings by severity and conclusion."""
    out = [f"{'id':<6}{'model':<22}{'high':>5}{'med':>4}{'low':>4}"
           f"  conclusion", "-" * WIDTH]
    for r in reports:
        n = {s: sum(f.severity == s for f in r.findings)
             for s in SEVERITY}
        out.append(f"{r.model:<6}{r.name[:21]:<22}{n['high']:>5}"
                   f"{n['medium']:>4}{n['low']:>4}  "
                   f"{conclude(r.findings)}")
    return out


def record(r: Report, measures: dict[str, str] | None = None) -> dict:
    """The report as data, in the form Chapter 29's register reads."""
    return {"model": r.model, "name": r.name, "date": str(r.date),
            "data_to": str(r.data_to), "validator": r.validator,
            "scope": r.scope, "conclusion": conclude(r.findings),
            "use": r.use, "confirmed": r.confirmed,
            "measures": measures or {},
            "findings": [asdict(f) for f in r.findings]}


def save(reports, measures: dict[str, dict] | None = None,
         path: Path = OUT) -> list[Path]:
    """Write reports.json (every report as data) and one text file per
    model, the report as rendered."""
    measures = measures or {}
    path.mkdir(parents=True, exist_ok=True)
    recs = [record(r, measures.get(r.model)) for r in reports]
    f = path / "reports.json"
    f.write_text(json.dumps({"date": str(VALIDATION_DATE),
                             "reports": recs}, indent=1) + "\n")
    out = [f]
    for r in reports:
        t = path / f"{r.model}.txt"
        t.write_text("\n".join(render(r, measures.get(r.model))) + "\n")
        out.append(t)
    return out


def load(path: Path = OUT) -> list[dict]:
    return json.loads((path / "reports.json").read_text())["reports"]


def register_entries(path: Path = OUT) -> dict[str, dict]:
    """What Chapter 29's register needs from each saved report: the
    year of the independent validation, its conclusion, and the open
    findings by severity."""
    out = {}
    for r in load(path):
        sev = [f["severity"] for f in r["findings"]]
        out[r["model"]] = {"validated": r["date"][:4],
                           "date": r["date"],
                           "conclusion": r["conclusion"],
                           **{s: sev.count(s) for s in SEVERITY}}
    return out


# ------------------------------------------- Fernhill's validations
# The validator's record of each validation: what was in scope, what
# the work confirmed, and what it found. The numbers quoted are those
# Chapter 23's listings printed; the conclusion is computed by
# `conclude`, never typed.
F = Finding
REPORTS = {r.model: r for r in [
    Report(
        "MK2R", "Mark II-R scorecard",
        scope=["data, sample and the definition of bad against the "
               "default the PD and the provision count",
               "implementation: the engine's scores against the "
               "saved points table",
               "ranking with intervals, on booked loans and with the "
               "bureau's retro outcomes; benchmarks Mark I, Mark II "
               "and the boosted challenger",
               "calibration of the scale by band; stability of the "
               "score and of each line",
               "overrides, fair lending and use beyond the first year"],
        use="deciding personal-loan applications at the cut-off of "
            "554; its score as an input to the 12-month PD",
        confirmed=[
            "sample rebuilt from the loan book row for row; every "
            "2025 score reproduced from the saved table",
            "every bad under its label is a default under the 2021 "
            "definition",
            "ranks better than Mark I on lender-visible outcomes, and "
            "ranks next year's defaults at every age of a loan",
            "score population stable: PSI at most 0.012 in any year"],
        findings=[
            F("MK2R-1", "medium",
              "The label is dpd90 in the first year; the provision "
              "counts dod2021 defaults in any year. The 56 bankruptcy "
              "defaults the label misses score near the average.",
              "State the bridge (Chapter 18's calibration on dod2021) "
              "in the document; label the next redevelopment on "
              "dod2021.", "23.2"),
            F("MK2R-2", "medium",
              "The scale over-promises bad rates on booked loans "
              "(3.14% against 2.50% out of time), most at 600 and "
              "above.",
              "Keep the scale out of every use as a probability; the "
              "PD and the price grid read the calibration.", "23.3"),
            F("MK2R-3", "high",
              "Approval of women relative to men was 0.957 in 2025, "
              "with an interval below one; the cause is not known.",
              "Owner to explain the gap within three months, with the "
              "income line tested first; report the ratio monthly.",
              "23.4"),
            F("MK2R-4", "medium",
              "At the same score, older borrowers go bad more often "
              "and the young less: the scale is hardest on the young.",
              "Accepted by the owner for now; recalibrate by age band "
              "or remove a time line at the next redevelopment.",
              "23.4"),
            F("MK2R-5", "medium",
              "The boosted challenger ranks better on the fairest "
              "evidence a lender has, by about three Gini points.",
              "Start the champion-challenger test on the "
              "disagreements in April, as Chapter 11 designed it.",
              "23.4"),
            F("MK2R-6", "low",
              "Income bins are in nominal dollars, so inflation moves "
              "applicants up the income line year by year.",
              "Review the income bins each year against wage growth.",
              "23.3"),
        ]),
    Report(
        "PD12", "12-month PD, personal",
        scope=["definition of default and the sample of loan-quarters",
               "grade-level binomial and Jeffreys tests, Hosmer-"
               "Lemeshow, out of time",
               "a yearly traffic-light backtest 2017-2025, each year "
               "scored by a model that never saw it",
               "point-in-time and through-the-cycle behaviour"],
        use="stage 1 and staging PDs for personal loans under the "
            "reporting date's scenarios; the TTC setting for capital",
        confirmed=[
            "nine yearly backtests green given the year's "
            "unemployment, including 2020",
            "every grade's PD inside the range its defaults allow at "
            "95%, out of time",
            "point in time as the provision needs: yearly PD and "
            "default rate correlate at 0.98"],
        findings=[
            F("PD12-1", "medium",
              "Grade 9, the scores just above the cut-off, is light: "
              "10.99% seen against 8.85% expected.",
              "Watch the 540-559 band monthly; recalibrate if it "
              "stays light for two quarters.", "23.5"),
            F("PD12-2", "medium",
              "The PD is only as good as the unemployment forecast "
              "fed to it: with no change assumed, 2020 lights red.",
              "Validate the scenario process with the provision "
              "engine; disclose the sensitivity.", "23.5"),
            F("PD12-3", "medium",
              "PDs are heavy for the safest grades (grades 5 and 6 saw "
              "35 defaults against 57 expected).",
              "Recalibrate the low end when a third year confirms it.",
              "23.5"),
            F("PD12-4", "low",
              "No out-of-time evidence was saved with the production "
              "fit.",
              "Run the leave-year-out backtest every year and save it.",
              "23.5"),
        ]),
    Report(
        "LGD", "Workout LGD",
        scope=["out-of-time backtest of the estimate for each year's "
               "defaults, 2019-2023",
               "treatment of unfinished workouts (censoring)",
               "cures, discounting and the downturn rule as built"],
        use="LGD by product for the provision and for capital, with "
            "the floors Chapter 21 applies",
        confirmed=[
            "the additive completion recovers mature years' LGDs; "
            "estimates sit within a few points of later outcomes"],
        findings=[
            F("LGD-1", "medium",
              "Out of time the estimate ran high by 2.2 to 4.5 points "
              "a year on average; a debt sale inside the pattern "
              "pulled the card estimate for 2020 down instead.",
              "Estimate the recovery pattern without debt sales and "
              "treat sales as a separate, priced decision.", "23.6"),
            F("LGD-2", "medium",
              "Up to a sixth of the recovery in the unsecured "
              "estimates is projected, not yet received; mortgage LGD "
              "rests on projection and 110 workouts.",
              "Report the projected share with the estimate; keep the "
              "mortgage floor.", "23.6"),
        ]),
    Report(
        "CCF", "Conversion factors",
        scope=["out-of-time backtest of card and overdraft factors on "
               "2023-2025 defaults",
               "stability of the revolver factor"],
        use="EAD on card, overdraft and commercial revolver limits",
        confirmed=["the card factors predict 2023-2025 exposure within "
                   "4%, in every band"],
        findings=[
            F("CCF-1", "medium",
              "The overdraft factor fitted to 2022 under-predicted the "
              "next three years' exposure by about an eighth.",
              "Re-estimate yearly on all defaults; add a margin until "
              "it settles.", "23.6"),
            F("CCF-2", "medium",
              "The revolver factor rests on 17 defaults.",
              "Accepted with its interval; add each new default.",
              "23.6"),
        ]),
    Report(
        "RATE", "Ballast rating model",
        scope=["ranking out of year with intervals, against Fernhill's "
               "model grade and the analysts",
               "each grade's PD tested both ways (Jeffreys)",
               "yearly backtest of the book; reproducibility"],
        use="the model grade at commercial reviews from 2026, with "
            "overrides recorded with their reasons",
        confirmed=["ranks at least as well as Fernhill's model, and is "
                   "rebuilt from its saved file"],
        findings=[
            F("RATE-1", "medium",
              "Grades 1 to 5 cannot be confirmed by 35 defaults, and "
              "grade 6's record says its PD is too high.",
              "Keep the master scale; report the Bayesian estimate "
              "beside it until the record can decide.", "23.7"),
            F("RATE-2", "medium",
              "The model is point in time; the grades' PDs are fixed. "
              "Its grades will move with the economy.",
              "Say so in the policy; review the mapping each year.",
              "23.7"),
            F("RATE-3", "medium",
              "A three-input version without size fits slightly "
              "better (Chapter 16).",
              "Choose between them before first use and record why.",
              "23.7"),
        ]),
    Report(
        "FRM", "Fernhill rating model",
        scope=["reproduction of the grades from the documented inputs",
               "ranking and the analysts' holds of its grades"],
        use="",
        confirmed=["its grades rank defaults well (Gini 0.857)"],
        findings=[
            F("FRM-1", "high",
              "The model cannot be reproduced: from leverage, cover "
              "and "
              "size its grade is matched only two times in three.",
              "Replace it with the Ballast rating model at the 2026 "
              "reviews, after RATE's conditions are met.", "23.7",
              blocks=True),
            F("FRM-2", "high",
              "Analysts held 195 grades the model wanted worse; held "
              "clients defaulted at 4.1% on a grade PD of 1.47%. No "
              "hold has a reason on file.",
              "Every override recorded with its reasons and approved "
              "by the credit function.", "23.7"),
        ]),
]}
