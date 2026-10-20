"""The credit memo: one document that puts a request, the analysis and
the recommendation in front of the credit committee.

A memo is written by an analyst, not generated; this module holds its
parts and lays them out the same way every time, so that a committee
reading its tenth memo of the morning finds the limit, the risks and
the conditions where it found them in the other nine.

    from ballast.commercial import memo as mm
    m = mm.Memo(borrower=..., request=..., ...)
    print("\\n".join(mm.render(m)))        # text, 68 characters wide
    print(mm.to_markdown(m))                # the same, as Markdown

The figures table comes from the spread (`key_figures`), so the memo
quotes the same numbers as the analysis, to the line.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

import pandas as pd

from ballast.commercial.structure import TermSheet

WIDTH = 68

# (ratio or line, label, format) for the figures table.
FIGURES = [
    ("revenue", "Revenue, $m", "m"),
    ("ebitda", "EBITDA, $m", "m"),
    ("total_debt", "Borrowings, $m", "m"),
    ("leverage", "Debt / EBITDA", "x"),
    ("interest_cover", "EBITDA / interest", "x"),
    ("receivable_days", "Receivable days", "d"),
    ("free_cash_flow", "Free cash flow, $m", "m"),
    ("payout", "Dividends / net income", "%"),
]


@dataclass
class Memo:
    """Everything a committee reads about one request."""
    borrower: str
    request: str
    prepared: str
    decision: str
    recommendation: str
    terms: TermSheet
    figures: list[tuple[str, list[str]]]
    figure_years: list[str]
    case_for: list[str] = field(default_factory=list)
    risks: list[tuple[str, str]] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    rating: str = ""


def _fmt(v: float, unit: str) -> str:
    if v != v:
        return ""
    if unit == "m":
        return f"{v / 1e8:,.1f}"
    if unit == "x":
        return f"{v:.2f}x"
    if unit == "%":
        return f"{v:.0%}"
    return f"{v:.0f}"


def key_figures(s: pd.DataFrame, r: pd.DataFrame,
                extra: dict[str, dict] | None = None
                ) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """The figures table: chosen lines and ratios by year.

    `s` is a spread and `r` its ratios (Chapter 14). `extra` adds
    columns such as a pro forma year: {heading: {key: value}}, with
    blanks for keys it does not give.
    """
    years = [str(y) for y in s.columns]
    extra = extra or {}
    rows = []
    for key, label, unit in FIGURES:
        src = s if key in s.index else r
        vals = [_fmt(float(v), unit) for v in src.loc[key]]
        vals += [_fmt(float(col.get(key, float("nan"))), unit)
                 for col in extra.values()]
        rows.append((label, vals))
    return years + list(extra), rows


def _wrap(text: str, width: int, first: str = "",
          rest: str = "") -> list[str]:
    return textwrap.wrap(text, width, initial_indent=first,
                         subsequent_indent=rest) or [first.rstrip()]


def _heading(title: str, width: int) -> list[str]:
    return ["", title.upper(), "-" * width]


def render(m: Memo, width: int = WIDTH) -> list[str]:
    """The memo as lines of text no wider than `width`."""
    t = m.terms
    out = ["CREDIT MEMORANDUM".center(width).rstrip(),
           "=" * width,
           f"Borrower   {m.borrower}",
           f"Request    {m.request}",
           f"Prepared   {m.prepared}",
           f"Decision   {m.decision.upper()}"]

    out += _heading("Recommendation", width)
    out += _wrap(m.recommendation, width)

    out += _heading("Facility proposed", width)
    fee = t.margin_bps * t.commitment_share
    terms = [
        ("Limit", f"${t.limit_cents / 100:,.0f}, {t.tenor_months} "
                  "months, committed, revolving"),
        ("Drawings", "lesser of limit and borrowing base "
                     f"({t.advance_receivables:.0%} eligible "
                     f"receivables, {t.advance_inventory:.0%} "
                     "eligible stock)"),
        ("Price", f"{t.reference} + {t.margin_bps} bps; "
                  f"{fee:.0f} bps undrawn; "
                  f"{t.arrangement_pct:.2%} arrangement"),
        ("Security", t.security),
        ("Covenants", f"debt/EBITDA <= {t.max_leverage:.2f}x; "
                      f"EBITDA/interest >= {t.min_cover:.2f}x; "
                      f"dividends <= {t.payout_cap:.0%} of prior "
                      "year's profit"),
    ]
    for label, text in terms:
        out += _wrap(text, width, f"{label:<11}", " " * 11)

    out += _heading("Figures", width)
    lw = width - 8 * len(m.figure_years)
    out.append(" " * lw + "".join(f"{y:>8}" for y in m.figure_years))
    for label, vals in m.figures:
        out.append(f"{label:<{lw}}" + "".join(f"{v:>8}" for v in vals))

    out += _heading("The case for lending", width)
    for item in m.case_for:
        out += _wrap(item, width, "+ ", "  ")

    out += _heading("Risks, and what the structure does", width)
    for risk, mitigant in m.risks:
        out += _wrap(risk, width, "- ", "  ")
        out += _wrap(mitigant, width, "  > ", "    ")

    out += _heading("Conditions before first drawing", width)
    for i, item in enumerate(m.conditions, 1):
        out += _wrap(item, width, f"{i}. ", "   ")

    if m.questions:
        out += _heading("Still to be answered", width)
        for item in m.questions:
            out += _wrap(item, width, "? ", "  ")

    if m.rating:
        out += _heading("Rating", width)
        out += _wrap(m.rating, width)
    return [line.rstrip() for line in out]


def to_markdown(m: Memo) -> str:
    """The same memo as Markdown, for the committee pack."""
    t = m.terms
    md = [f"# Credit memorandum: {m.borrower}", "",
          f"**Request:** {m.request}  ",
          f"**Prepared:** {m.prepared}  ",
          f"**Decision:** {m.decision}", "",
          "## Recommendation", "", m.recommendation, "",
          "## Facility proposed", ""]
    md += [f"| {label} | {text} |" if i else
           f"| {label} | {text} |\n|---|---|"
           for i, (label, text) in enumerate(t.rows()) if text]
    md += ["", "## Figures", "",
           "| | " + " | ".join(m.figure_years) + " |",
           "|---|" + "---:|" * len(m.figure_years)]
    md += [f"| {label} | " + " | ".join(vals) + " |"
           for label, vals in m.figures]
    md += ["", "## The case for lending", ""]
    md += [f"- {x}" for x in m.case_for]
    md += ["", "## Risks, and what the structure does", ""]
    md += [f"- **{r}** {x}" for r, x in m.risks]
    md += ["", "## Conditions before first drawing", ""]
    md += [f"{i}. {x}" for i, x in enumerate(m.conditions, 1)]
    if m.questions:
        md += ["", "## Still to be answered", ""]
        md += [f"- {x}" for x in m.questions]
    if m.rating:
        md += ["", "## Rating", "", m.rating]
    return "\n".join(md) + "\n"
