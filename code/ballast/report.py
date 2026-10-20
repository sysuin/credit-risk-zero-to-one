"""The risk committee pack (Chapter 27).

One document for the board risk committee's January meeting, built
from what Ballast saved and from nothing else: the risk appetite
statement and the plan (appetite.py), the provision (Chapter 20),
capital (21), the loss distribution (22), the December monitoring
pack (24), collections' treatment (25), the stress test (26) and
the governance files (29). Every line fits WIDTH characters, so the
pack prints as it reads.

    text = pack()          # the pack, as Markdown
    save(text)             # data/ballast/report/pack_2026-01.md
"""
from __future__ import annotations

import textwrap

import pandas as pd

from ballast import appetite as ap
from ballast import collections as coll
from ballast import ecl, stress
from ballast import portfolio as pf
from ballast.config import AS_OF, BALLAST

OUT = BALLAST / "report"
WIDTH = 68
M = 1e8                     # cents in a million dollars
STATUS = {"green": "GREEN", "amber": "AMBER", "red": "RED"}
TREATMENTS = {"call_first": "a phone call", "sms_first": "a text"}


# ------------------------------------------------------------ helpers

def para(text: str, indent: str = "") -> list[str]:
    """A paragraph wrapped to the page."""
    return textwrap.wrap(text, WIDTH, initial_indent=indent,
                         subsequent_indent=" " * len(indent),
                         break_on_hyphens=False)


def item(n: int, text: str) -> list[str]:
    """A numbered item, its lines after the first indented."""
    first = f"{n}. "
    return textwrap.wrap(text, WIDTH, initial_indent=first,
                         subsequent_indent=" " * len(first),
                         break_on_hyphens=False)


def block(lines: list[str]) -> list[str]:
    """Fixed-width lines, fenced so that Markdown keeps them as set."""
    return ["```"] + [s.rstrip() for s in lines] + ["```"]


def heading(n: int, title: str) -> list[str]:
    return ["", f"## {n} {title}", ""]


def money(cents: float) -> str:
    return f"${cents / M:,.1f}m"


def _status(st: pd.DataFrame, mid: str) -> dict:
    return st.set_index("id").loc[mid].to_dict()


def _alerts() -> list[str]:
    """The FOR ATTENTION list of the December monitoring pack."""
    text = (BALLAST / "monitoring" / f"pack_{AS_OF:%Y-%m}.txt"
            ).read_text().splitlines()
    i = text.index("FOR ATTENTION")
    out = []
    for line in text[i + 1:]:
        if not line.strip():
            break
        out.append(line.strip().split(". ", 1)[1])
    return out


# ------------------------------------------------------------ sections

def _headline(a: dict, st: pd.DataFrame) -> list[str]:
    c1, c2, c3 = (_status(st, k) for k in ("C1", "C2", "C3"))
    q1, q3 = _status(st, "Q1"), _status(st, "Q3")
    ret = {r["segment"]: r for r in a["returns"]}
    retail = [r for k, r in ret.items() if k in ap.RETAIL]
    rr = sum(r["ret"] for r in retail) / sum(r["capital"]
                                            for r in retail)
    k = st.status.value_counts()
    c = a["capital"]
    over = c["cet1"] - a["target"]["target"] * c["sa_rwa"]
    spare = c["cet1"] - c["requirement"] * c["sa_rwa"]
    lines = []
    for s in (
        f"CET1 is {c1['value']:.1%} against a target of "
        f"{c1['appetite']:.1%}: inside appetite, {money(over)} above "
        f"the target. The {money(spare)} above the requirement is not "
        "spare.",
        f"The supervisor's scenario takes CET1 to {c2['value']:.1%}, "
        f"below its tolerance of {c2['tolerance']:.1%}. The watchlist "
        f"(grades 9-10, {money(q1['value'])} of exposure) is the cause; "
        f"the scenario can carry {money(q1['appetite'])} of it.",
        f"Economic capital is {c3['value']:.1%} of CET1 against a "
        f"ceiling of {c3['appetite']:.1%}.",
        f"The commercial book returns {q3['value']:.1%} on its capital "
        f"before running costs; retail returns {rr:.1%}.",
        f"Of {len(st)} appetite metrics, {k.get('red', 0)} are red, "
        f"{k.get('amber', 0)} amber and {k.get('green', 0)} green."):
        lines += para(s, "- ")
    return lines


def _dashboard(st: pd.DataFrame) -> list[str]:
    def th(v, unit, higher):
        return (">=" if higher else "<=") + ap.fmt(v, unit)
    rows = [f"{'':<4}{'metric':<28}{'now':>8}{'appetite':>10}"
            f"{'status':>8}"]
    area = None
    for _, r in st.iterrows():
        if r.area != area:
            area = r.area
            rows.append(area.upper())
        rows.append(f"{r.id:<4}{r.metric:<28}"
                    f"{ap.fmt(r.value, r.unit):>8}"
                    f"{th(r.appetite, r.unit, r.higher):>10}"
                    f"{STATUS[r.status]:>8}")
    out = block(rows)
    out += [""] + para("Green: inside the appetite. Amber: beyond it, "
                       "inside the tolerance. Red: beyond the "
                       "tolerance. Thresholds and owners are in the "
                       "statement (appendix to the board paper).")
    return out


def _provisions() -> list[str]:
    e = ecl.load()
    g = e.pivot_table(index="segment", columns="stage", values="ecl",
                      aggfunc="sum").fillna(0)
    rows = [f"{'$m':<12}{'stage 1':>9}{'stage 2':>9}{'stage 3':>9}"
            f"{'total':>9}{'cover':>8}"]
    for seg in ("retail", "commercial"):
        bal = e.balance_cents[e.segment == seg].sum()
        rows.append(f"{seg:<12}" + "".join(
            f"{g.loc[seg].get(s, 0) / M:>9.1f}" for s in (1, 2, 3))
            + f"{g.loc[seg].sum() / M:>9.1f}"
            f"{g.loc[seg].sum() / bal:>8.2%}")
    rows.append(f"{'total':<12}" + "".join(
        f"{g[s].sum() / M:>9.1f}" for s in (1, 2, 3))
        + f"{e.ecl.sum() / M:>9.1f}"
        f"{e.ecl.sum() / e.balance_cents.sum():>8.2%}")
    sc = {s: e[f"ecl_{s}"].sum() for s in
          ("upside", "base", "downside", "severe")}
    out = block(rows)
    n2 = int((e.stage == 2).sum())
    b2 = e.balance_cents[e.stage == 2].sum() / e.balance_cents.sum()
    y = stress.load()["years"]
    s26 = y[(y.scenario == "stress_2026") & (y.year == 2026)].iloc[0]
    out += [""] + para(
        "By scenario: " + ", ".join(f"{k} {v / M:,.1f}" for k, v in
                                    sc.items())
        + f" ($m); weighted {money(e.ecl.sum())}, "
        f"{e.ecl.sum() / sc['base'] - 1:.1%} above the base. "
        f"Stage 2 holds {n2:,} accounts and {b2:.1%} of the balance. "
        f"CECL, computed alongside, {money(e.cecl.sum())}. In the "
        "supervisor's scenario the provision would be "
        f"{money(s26.provision)} at the end of 2026.")
    return out


def _capital(a: dict) -> list[str]:
    c = a["capital"]
    t = a["target"]
    s = stress.load()
    y, summ = s["years"], s["summary"]
    lo = pf.load()
    t1 = (c["cet1"] + c["at1"]) / c["sa_rwa"]
    tot = (c["cet1"] + c["at1"] + c["tier2"]) / c["sa_rwa"]
    out = para(f"CET1 {money(c['cet1'])} on standardised RWA of "
               f"${c['sa_rwa'] / M:,.0f}m: CET1 {c['cet1_ratio']:.1%}, "
               f"Tier 1 {t1:.1%}, total {tot:.1%}. Requirement "
               f"{c['requirement']:.1%}; target {t['target']:.1%}; "
               f"tolerance {t['tolerance']:.1%}. Economic capital at "
               f"99.9% {money(lo['ec_999'])}, "
               f"{lo['ec_999'] / c['cet1']:.1%} of CET1.")
    rows = [f"{'three years':<16}{'trough':>8}{'losses':>9}"
            f"{'CET1 used':>11}"]
    names = {"base": "base", "severe": "severe (own)",
             "stress_2026": "supervisor's"}
    for k, label in names.items():
        g = y[y.scenario == k]
        rows.append(f"{label:<16}{summ['trough_sa'][k]:>8.1%}"
                    f"{g.loss.sum() / M:>9,.0f}"
                    f"{(c['cet1'] - g.cet1.min()) / M:>11,.0f}")
    out += [""] + block(rows)
    r = s["reverse"]["stress_2026"]
    out += [""] + para(
        f"Reverse stress: {r['k']:.2f} of the supervisor's scenario "
        f"takes CET1 to {c['requirement']:.1%} (unemployment "
        f"{r['peak_u']:.1f}%, policy rate {r['peak_policy']:.1f}%).")
    return out


def _concentrations(a: dict) -> list[str]:
    c = a["capital"]
    lim = ap.NAME[0] * c["tier1"]
    rows = [f"{'client':<27}{'grade':>6}{'EAD $m':>8}{'of T1':>8}"
            f"{'limit':>9}"]
    for r in a["names"][:6]:
        rows.append(f"{r['name']:<27}{r['grade']:>6}"
                    f"{r['ead'] / M:>8.1f}{r['share']:>8.1%}"
                    f"{'over' if r['ead'] > lim else '':>9}")
    out = block(rows)
    sec = a["sectors"]
    top = max(sec, key=sec.get)
    st = pd.DataFrame(a["statement"])
    n3, n4 = _status(st, "N3"), _status(st, "N4")
    out += [""] + para(
        f"{a['names_over']} clients exceed the limit of "
        f"{ap.NAME[0]:.0%} of Tier 1 ({money(lim)}). Largest sector "
        f"{top} {sec[top]:.1%} of commercial exposure; largest region "
        f"{n3['value']:.1%} of retail; commercial lending "
        f"{n4['value']:.1%} of the book. Watchlist exposure "
        f"{money(a['watchlist']['now'])} against a limit of "
        f"{money(a['watchlist']['appetite'])}.")
    return out


def _monitoring() -> list[str]:
    out = para("From the December monitoring pack, items beyond their "
               "limits:")
    out += [""]
    for i, s in enumerate(_alerts(), 1):
        out += item(i, s)
    t = coll.TREATMENT
    out += [""] + para(
        "For noting: collections now open with "
        f"{TREATMENTS[t['champion']]} at the first missed payment, with "
        f"{t['challenger_share']:.0%} of accounts given "
        f"{TREATMENTS[t['challenger']]} first so that the effect is "
        "still measured.")
    return out


def _models(a: dict) -> list[str]:
    mr = a["model_risk"]
    out = para(f"{len(mr['unvalidated'])} tier 1 models in use have no "
               "independent validation on file: "
               + ", ".join(mr["unvalidated"]) + ". "
               f"The findings log holds {mr['logged']} findings; "
               f"{len(mr['open_high'])} high findings are open, and "
               "none has a date for its fix:")
    out += [""]
    rows = [f"{f['id']:<5}{f['model']:<6}{f['issue']}"
            for f in mr["open_high"]]
    return out + block(rows)


def _plan(a: dict) -> list[str]:
    p = a["plan"]
    rows = [f"{'supervisor scenario, cumulative':<38}{'trough':>8}"
            f"{'watchlist':>11}"]
    rows.append(f"{'today':<38}{p['today']['stress_2026']:>8.1%}"
                f"{a['watchlist']['now'] / M:>11,.0f}")
    for s in p["steps"]:
        rows.append(f"{s['label']:<38}{s['trough']:>8.1%}"
                    f"{s['watchlist'] / M:>11,.0f}")
    out = block(rows)
    lo = pf.load()
    out += [""] + para(
        "Each step is measured as if complete, on Chapter 26's static "
        "book. The first four are the plan for 2026; with them, "
        f"Fernhill's own severe scenario leaves CET1 at "
        f"{p['whole']['severe']:.1%} and economic capital falls from "
        f"{money(lo['ec_999'])} to {money(p['ec'])}. The fifth, the "
        "watchlist run down to its limit, is the work of 2027.")
    return out


def decisions(a: dict) -> list[str]:
    """What the committee is asked to decide, from the statement and
    the plan."""
    c, t, p = a["capital"], a["target"], a["plan"]
    st = pd.DataFrame(a["statement"])
    wl = a["watchlist"]
    lo = pf.load()
    contrib = ap.allocate(pf.load_contributions(), lo["ec_999"])
    auto = contrib[contrib.segment == "auto"]
    k = st.status.value_counts()
    big = [r["name"] for r in a["names"] if r["share"] > ap.NAME[0]]
    gap = ", ".join(f"grade {g} +{v:.0f}" for g, v in
                    p["gap_bps"].items())
    unval = a["model_risk"]["unvalidated"]
    spare = c["cet1"] - c["requirement"] * c["sa_rwa"]
    return [
        f"Recommend the 2026 risk appetite statement ({len(st)} "
        f"metrics; today {k.get('red', 0)} red, {k.get('amber', 0)} "
        "amber) to the board in February.",
        f"Hold CET1 at or above the {t['target']:.1%} target. Decline "
        f"the proposal to return or lend the {money(spare)} above the "
        "requirement, and make no distribution while the supervisor's "
        f"scenario leaves CET1 below {c['requirement']:.1%}.",
        "Approve the watchlist plan: no new money for grades 9-10; "
        "undrawn revolver headroom cancelled at review; facilities "
        "maturing in 2026 not renewed; watchlist exposure down to "
        f"{money(wl['appetite'])} by December 2027.",
        f"Approve a single-client limit of {ap.NAME[0]:.0%} of Tier 1. "
        f"Allow the {len(big)} clients above it ("
        + ", ".join(big) + ") as exceptions until December 2026, to "
        "be reduced by participations or bought protection.",
        f"Reprice grades 5-8 at their 2026 reviews ({gap} bps), and "
        "approve new commercial lending only at a margin that earns "
        f"the {ap.HURDLE:.0%} hurdle on its capital.",
        "Let retail lending grow within its limits, and direct the "
        "head of retail credit to re-set Mark I's bureau points for "
        "cards, car loans and mortgages (open since July 2019).",
        f"Approve a validation plan for the {len(unval)} tier 1 models "
        "in use without one, the provision engine and Mark I first, "
        "with a date for every open high finding.",
        "Aim any risk transfer bought in 2026 at the commercial clients "
        "above the limit, not at the retail book: the car loans, "
        f"{money(auto.ead.sum())} of exposure, carry "
        f"{money(auto.ec.sum())} of the {money(lo['ec_999'])} of "
        "economic capital."]


# ---------------------------------------------------------------- pack

def pack(a: dict | None = None) -> str:
    """The pack for the January 2026 meeting, as Markdown no wider
    than WIDTH."""
    a = a or ap.load()
    st = pd.DataFrame(a["statement"])
    meeting = pd.Timestamp(a["meeting"])
    lines = ["# FERNHILL BANK: RISK COMMITTEE PACK", "",
             f"Board risk committee, {meeting:%A} {meeting.day} "
             f"{meeting:%B %Y}.",
             f"Position at {AS_OF.day} {AS_OF:%B %Y}; produced by "
             "Ballast."]
    sections = [("Headline", _headline(a, st)),
                ("Risk appetite dashboard", _dashboard(st)),
                ("Provisions", _provisions()),
                ("Capital and stress", _capital(a)),
                ("Concentrations", _concentrations(a)),
                ("Monitoring alerts", _monitoring()),
                ("Model risk", _models(a)),
                ("The commercial plan, measured", _plan(a))]
    for n, (title, body) in enumerate(sections, 1):
        lines += heading(n, title) + body
    lines += heading(len(sections) + 1, "Decisions requested")
    for i, d in enumerate(decisions(a), 1):
        lines += item(i, d)
    wide = [s for s in lines if len(s) > WIDTH]
    if wide:
        raise ValueError(f"pack lines wider than {WIDTH}: {wide}")
    return "\n".join(lines) + "\n"


def save(text: str, month: str = "2026-01") -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"pack_{month}.md"
    f.write_text(text)
    return str(f.relative_to(BALLAST.parent.parent))
