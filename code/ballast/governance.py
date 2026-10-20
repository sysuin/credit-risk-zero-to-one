"""Governance: Fernhill's model inventory and tiers, model documents,
the validation findings log, who does what, lending authority and
the override record.

Most of this module is data: the records a bank keeps about its own
models and its own rules, written where a reviewer can read them.
The functions compute what can be computed from the loan book and
from what Ballast has saved, so that the inventory is generated, not
typed, and says the same thing on every run.

    import fernhill
    from ballast import governance as gv
    con = fernhill.connect()
    inv = gv.build_inventory(con)        # one dict per model, tiered
    gv.save_inventory(inv)               # data/ballast/governance/
    gv.register_lines(inv)               # the register, 68 wide
    text, status = gv.document("MK2R", inv)
    gv.approver(exposure_cents, grade)   # who may approve it
    gv.low_side_overrides(con)           # the retail override record

Ballast never reads the truth here: governance works on what a bank
can see.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ballast.commercial.rating import MASTER_SCALE
from ballast.config import AS_OF, BALLAST

OUT = BALLAST / "governance"

# ------------------------------------------- the tiering rule
# Fernhill's model risk policy. Materiality asks what the output
# does: enters the accounts or capital ("external"), decides or
# prices for customers ("decide"), or informs people who then decide
# ("inform"). Evidence asks how far the output can be trusted.
HIGH_DECIDED_CENTS = 100_000_000_000   # $1bn decided a year: high
THIN_EVIDENCE = 50                     # fewer defaults: elevated
LEVEL = {"external": "high", "decide": "medium", "inform": "low"}
TIER_OF = {"high": 1, "medium": 2, "low": 3}
# What each tier buys: validation before use, the longest gap between
# full validations (months), and how often the owner monitors.
TIER_POLICY = {1: ("full, before use", 24, "monthly"),
               2: ("full, before use", 36, "quarterly"),
               3: ("light, before use", 60, "yearly")}


def materiality_level(use: str, cents: int | None) -> str:
    """High, medium or low, from what the output does and the money
    it decides."""
    if use == "decide" and cents is not None \
            and cents >= HIGH_DECIDED_CENTS:
        return "high"
    return LEVEL[use]


def elevated(evidence: int | None, judgement: str) -> bool:
    """True when the output cannot be checked well: fewer than
    THIN_EVIDENCE defaults behind it, no development data held, or a
    judgement or method that outcomes cannot test."""
    return evidence is None or evidence < THIN_EVIDENCE \
        or bool(judgement)


def own_tier(level: str, is_elevated: bool) -> int:
    """Materiality sets the tier; doubtful evidence raises it one."""
    return max(1, TIER_OF[level] - int(is_elevated))


def inherit(own: dict[str, int | None],
            inputs: dict[str, list[str]]) -> dict[str, int | None]:
    """A model takes the highest tier (lowest number) of any model in
    use that consumes its output, however indirectly."""
    users: dict[str, list[str]] = {k: [] for k in own}
    for k, ins in inputs.items():
        for i in ins:
            users[i].append(k)
    final: dict[str, int | None] = {}

    def tier(k, seen=()):
        if k in final:
            return final[k]
        t = own[k]
        for u in users[k]:
            if u in seen or own[u] is None:
                continue
            tu = tier(u, seen + (k,))
            t = tu if t is None else min(t, tu)
        final[k] = t
        return t

    for k in own:
        tier(k)
    return final


# --------------------------------------------- the model register
# Fernhill's records about each model: what a person decides and
# writes down. Materiality and evidence are computed from the book.
#   use       external / decide / inform
#   size      how materiality is measured: ("lending", products)
#             2025 lending decided; ("ead", products) exposure on 31
#             December 2025; ("listed",) listed clients' exposure;
#             ("behind",) retail exposure in arrears; ("pool",) the
#             proposed securitisation pool; ("none",)
#   evidence  how the defaults behind it are counted (see evidence())
#   inputs    models whose output it uses when it runs
#   validated the last independent validation on Fernhill's file
#             before Ballast; a validation saved by Chapter 23's
#             validators (ballast.validation) replaces it when built
REGISTER = [
    dict(id="MK1", name="Mark I scorecard",
         purpose="decide card, car-loan and mortgage applications",
         owner="head of retail credit", developer="Fernhill, 2015",
         status="in use", use="decide",
         size=("lending", ("card", "auto", "mortgage")),
         evidence="not held", judgement="", inputs=[],
         artefacts=["code/ballast/decision/policy.py"],
         validated="2015",
         not_for="personal loans from January 2026; any use as a PD"),
    dict(id="MK2", name="Mark II scorecard",
         purpose="rank personal-loan applicants (superseded)",
         owner="head of retail credit", developer="risk modelling",
         status="not adopted", use="decide", size=("none",),
         evidence="mark2", judgement="", inputs=[],
         artefacts=["data/ballast/mark2/scorecard.json",
                    "data/ballast/mark2/model.json"],
         validated="", not_for="any decision"),
    dict(id="MK2R", name="Mark II-R scorecard",
         purpose="decide personal-loan applications from April 2026",
         owner="head of retail credit", developer="risk modelling",
         status="approved", use="decide",
         size=("lending", ("personal",)), evidence="mark2r",
         judgement="", inputs=[],
         artefacts=["data/ballast/reject/mark2_retro_ws.json",
                    "data/ballast/decision/policy.json"],
         validated="",
         not_for="a probability of default without Chapter 18's "
                 "calibration; cards, car loans, mortgages"),
    dict(id="CHAL", name="Boosted challenger",
         purpose="benchmark Mark II-R; decide the test arm",
         owner="head of retail credit", developer="risk modelling",
         status="benchmark", use="decide", size=("none",),
         evidence="mark2", judgement="boosted trees: no points table",
         inputs=[], artefacts=["data/ballast/challenger/model.txt",
                               "data/ballast/challenger/"
                               "challenger.json"],
         validated="", not_for="decisions outside the test arm"),
    dict(id="SME1", name="SME-1 scorecard",
         purpose="decide small-business loans and overdrafts",
         owner="head of small-business lending",
         developer="Fernhill, 2015", status="in use", use="decide",
         size=("lending", ("sme_term", "sme_overdraft")),
         evidence="not held", judgement="expert weights, not fitted",
         inputs=[], artefacts=["code/ballast/commercial/sme.py"],
         validated="2015", not_for="emergency loans; a PD"),
    dict(id="SME1B", name="SME-1 with bank data",
         purpose="replace SME-1 if the shadow run supports it",
         owner="head of small-business lending",
         developer="risk modelling", status="shadow", use="inform",
         size=("none",), evidence="sme_bank", judgement="",
         inputs=["SME1"], artefacts=["code/ballast/monitoring.py"],
         validated="", not_for="any decision while in shadow"),
    dict(id="FRM", name="Fernhill rating model",
         purpose="model grade for commercial clients",
         owner="chief credit officer", developer="Fernhill, 2017",
         status="in use", use="external",
         size=("ead", ("commercial_term", "commercial_revolver")),
         evidence="rating", judgement="", inputs=[],
         artefacts=[], validated="2017",
         not_for="small businesses; a grade without analyst review"),
    dict(id="RATE", name="Ballast rating model",
         purpose="model grade and PD for commercial clients",
         owner="chief credit officer", developer="risk modelling",
         status="proposed", use="external",
         size=("ead", ("commercial_term", "commercial_revolver")),
         evidence="rating", judgement="", inputs=[],
         artefacts=["data/ballast/rating/model.json"],
         validated="", not_for="small businesses"),
    dict(id="MERT", name="Merton market signals",
         purpose="prompt reviews of listed clients",
         owner="chief credit officer", developer="risk modelling",
         status="in use", use="inform", size=("listed",),
         evidence="listed", judgement="risk-neutral, not real-world",
         inputs=[], artefacts=["code/ballast/market.py"],
         validated="", not_for="provisions, capital or a grade"),
    dict(id="PD12", name="12-month PD",
         purpose="first-year PD for staging and stage 1",
         owner="head of credit risk", developer="risk modelling",
         status="in use", use="external",
         size=("ead", ("personal",)), evidence="defaults_personal",
         judgement="", inputs=["MK2R"],
         artefacts=["data/ballast/parameters/pd_calibration.json",
                    "data/ballast/parameters/pd_model.json"],
         validated="", not_for="capital without the TTC setting"),
    dict(id="HAZ", name="Lifetime PD hazards",
         purpose="PD term structures by product, band and economy",
         owner="head of credit risk", developer="risk modelling",
         status="in use", use="external",
         size=("ead", ("personal", "card", "auto", "mortgage",
                       "sme_term", "sme_overdraft",
                       "sme_emergency")),
         evidence="defaults_retail", judgement="",
         inputs=["MK2R", "MK1"],
         artefacts=["data/ballast/parameters/pd_hazard.json",
                    "data/ballast/parameters/"
                    "pd_term_structures.parquet"],
         validated="", not_for="commercial clients"),
    dict(id="LGD", name="Workout LGD",
         purpose="loss given default by product, with downturn",
         owner="head of credit risk", developer="risk modelling",
         status="in use", use="external", size=("ead", "all"),
         evidence="workouts", judgement="", inputs=[],
         artefacts=["data/ballast/parameters/lgd.json"],
         validated="", not_for="mortgages in negative equity"),
    dict(id="CCF", name="Conversion factors (EAD)",
         purpose="exposure at default on limits",
         owner="head of credit risk", developer="risk modelling",
         status="in use", use="external",
         size=("ead", ("card", "sme_overdraft",
                       "commercial_revolver")),
         evidence="revolvers", judgement="", inputs=[],
         artefacts=["data/ballast/parameters/ead.json"],
         validated="", not_for="instalment loans"),
    dict(id="ECL", name="IFRS 9 provision engine",
         purpose="the provision in the accounts; CECL alongside",
         owner="chief financial officer",
         developer="risk modelling", status="in use",
         use="external", size=("ead", "all"), evidence="components",
         judgement="scenario weights and overlays",
         inputs=["PD12", "HAZ", "LGD", "CCF", "FRM"],
         artefacts=["data/ballast/ecl/ecl_2025-12-31.parquet"],
         validated="", not_for="regulatory capital"),
    dict(id="CAP", name="Regulatory capital",
         purpose="risk-weighted assets, both approaches",
         owner="chief financial officer",
         developer="risk modelling", status="built",
         use="external", size=("ead", "all"), evidence="components",
         judgement="", inputs=["HAZ", "LGD", "CCF", "FRM"],
         artefacts=["code/ballast/capital.py"],
         validated="", not_for="pricing without a hurdle decision"),
    dict(id="BEH", name="Behavioural scores",
         purpose="rank existing card and loan customers",
         owner="head of retail credit", developer="risk modelling",
         status="in use", use="inform",
         size=("ead", ("card", "personal")),
         evidence="defaults_card", judgement="", inputs=["MK1"],
         artefacts=["data/ballast/monitoring/behaviour.json"],
         validated="", not_for="limit increases until validated"),
    dict(id="CURE", name="Collections cure model",
         purpose="order the collections queue",
         owner="head of collections", developer="risk modelling",
         status="in use", use="inform", size=("behind",),
         evidence="entries", judgement="", inputs=["BMAP"],
         artefacts=["code/ballast/collections.py"],
         validated="", not_for="choosing whom not to contact"),
    dict(id="FRAUD", name="Application fraud rules",
         purpose="refer suspected first-party fraud",
         owner="head of retail credit", developer="risk modelling",
         status="built", use="decide",
         size=("lending", ("personal",)), evidence="never_paid",
         judgement="", inputs=[],
         artefacts=["code/ballast/fraud.py"],
         validated="", not_for="declining without review"),
    dict(id="PRICE", name="Personal-loan price grid",
         purpose="price personal loans by Mark II-R tier",
         owner="head of retail lending", developer="risk modelling",
         status="approved", use="decide",
         size=("lending", ("personal",)), evidence="defaults_personal",
         judgement="", inputs=["MK2R"],
         artefacts=["data/ballast/pricing/pricing.json"],
         validated="", not_for="other products"),
    dict(id="SEC", name="Securitisation cash flows",
         purpose="value the proposed sale of car loans",
         owner="treasurer", developer="risk modelling",
         status="proposal", use="inform", size=("pool",),
         evidence="defaults_auto",
         judgement="default correlation cannot be observed",
         inputs=["HAZ", "LGD"],
         artefacts=["data/ballast/securitisation/deal.json"],
         validated="", not_for="capital relief without Chapter 21"),
    dict(id="BMAP", name="Bureau v2-to-v3 map",
         purpose="put old bureau scores on version 3's scale",
         owner="head of credit risk", developer="risk modelling",
         status="in use", use="inform", size=("none",),
         evidence="bureau_map", judgement="", inputs=[],
         artefacts=["data/ballast/mark2/bureau_v2_to_v3.csv"],
         validated="", not_for="scores from other bureaux"),
]
IN_USE = {"in use"}
LIVE = {"in use", "approved"}      # deciding today, or from April


def validations() -> dict[str, dict]:
    """The independent validations Chapter 23's validators saved:
    model id -> year, date, conclusion and findings by severity. Empty
    when no report has been saved."""
    from ballast import validation
    if not (validation.OUT / "reports.json").exists():
        return {}
    return validation.register_entries()


def validation_findings() -> list[dict]:
    """Every finding in the saved validation reports, with its model
    and the report's conclusion."""
    from ballast import validation
    if not (validation.OUT / "reports.json").exists():
        return []
    return [dict(f, model=r["model"], conclusion=r["conclusion"])
            for r in validation.load() for f in r["findings"]]


def _lending(con, products) -> int:
    """New lending booked in 2025 on these products (cents): loan
    amounts, and opening limits for cards and overdrafts."""
    ps = ", ".join(f"'{p}'" for p in products)
    return int(con.execute(f"""
        SELECT coalesce(sum(amount_cents), 0) FROM accounts
        WHERE year(open_date) = {AS_OF.year}
          AND predecessor_id IS NULL AND product IN ({ps})
        """).fetchone()[0])


def _ecl() -> pd.DataFrame:
    return pd.read_parquet(BALLAST / "ecl" /
                           f"ecl_{AS_OF:%Y-%m-%d}.parquet")


def materiality_cents(con, size, ecl=None) -> int | None:
    """The money behind a model, as its register entry measures it."""
    kind = size[0]
    if kind == "none":
        return None
    if kind == "lending":
        return _lending(con, size[1])
    if kind == "pool":
        deal = json.loads((BALLAST / "securitisation" /
                           "deal.json").read_text())
        return int(deal["pool_cents"])
    ecl = _ecl() if ecl is None else ecl
    if kind == "ead":
        rows = ecl if size[1] == "all" else \
            ecl[ecl["product"].isin(size[1])]
        return int(rows["ead_cents"].sum())
    if kind == "listed":
        listed = {r[0] for r in con.execute(
            "SELECT company_id FROM companies WHERE listed").fetchall()}
        com = ecl[ecl["segment"] == "commercial"]
        mask = com["account_id"].str.split("-").str[0].isin(listed)
        return int(com.loc[mask, "ead_cents"].sum())
    if kind == "behind":
        ret = ecl[ecl["segment"] == "retail"]
        return int(ret.loc[(ret["stage"] == 3) |
                           (ret["reason"] == "arrears"),
                           "ead_cents"].sum())
    raise ValueError(f"unknown size {size!r}")


def _defaults(con, products) -> int:
    ps = ", ".join(f"'{p}'" for p in products)
    return int(con.execute(f"""
        SELECT count(*) FROM defaults d JOIN accounts a
          USING (account_id) WHERE a.product IN ({ps})""").fetchone()[0])


def evidence(con, kind: str) -> int | None:
    """Defaults (or bads, or events) behind a model's estimates; None
    when Fernhill holds no development data."""
    if kind in ("not held", "components"):
        return None
    if kind == "mark2":
        s = json.loads((BALLAST / "mark2" / "sample.json").read_text())
        return int(s["counts"]["train"]["bads"])
    if kind == "mark2r":
        d = json.loads((BALLAST / "reject" /
                        "mark2_retro_ws.json").read_text())
        return int(round(d["rows_weighted"] * d["bad_share"]))
    if kind == "rating":
        m = json.loads((BALLAST / "rating" / "model.json").read_text())
        return int(m["defaults"])
    if kind == "listed":
        return int(con.execute("""SELECT count(*) FROM
            corporate_defaults JOIN companies USING (company_id)
            WHERE listed""").fetchone()[0])
    if kind == "workouts":
        g = json.loads((BALLAST / "parameters" / "lgd.json").read_text())
        return int(sum(p["workouts"] for p in g["products"].values()))
    if kind == "revolvers":
        from ballast.parameters import ead
        return len(ead.revolver_sample(con))
    if kind == "sme_bank":
        from ballast.commercial import sme
        s = sme.sample(con)
        return int(s.loc[s["ob"].astype(bool), "bad"].sum())
    if kind == "entries":
        return int(con.execute("""SELECT count(*) FROM collections
            WHERE action = 'reminder'""").fetchone()[0])
    if kind == "never_paid":
        from ballast import fraud
        f = fraud.first_payments(con, "personal")
        return int(f["never_paid"].sum())
    if kind == "bureau_map":
        return int(con.execute("""SELECT count(*) FROM applications
            WHERE app_date BETWEEN '2019-01-01' AND '2019-12-31'
              AND bureau_hit""").fetchone()[0])
    products = {"defaults_personal": ("personal",),
                "defaults_card": ("card", "personal"),
                "defaults_auto": ("auto",),
                "defaults_retail": ("personal", "card", "auto",
                                    "mortgage", "sme_term",
                                    "sme_overdraft", "sme_emergency")}
    return _defaults(con, products[kind])


def _due(validated: str, tier: int | None, status: str,
         conclusion: str = "") -> str:
    """When the next independent validation is due under the tier's
    policy: 'blocked' (validated and not approved), 'overdue', 'now'
    (in use, never validated), 'pre-use', or the year."""
    if tier is None:
        return "-"
    if conclusion == "not approved":
        return "blocked"
    if not validated:
        return "now" if status in IN_USE else "pre-use"
    months = TIER_POLICY[tier][1]
    due = dt.date(int(validated) + math.ceil(months / 12), 12, 31)
    return "overdue" if due < AS_OF else str(due.year)


def build_inventory(con, register=REGISTER) -> list[dict]:
    """Every model in the register with its materiality, evidence and
    tier computed, and the models that use it."""
    ecl = _ecl()
    done = validations()
    rows = []
    for r in register:
        e = dict(r)
        v = done.get(r["id"])
        e["conclusion"] = v["conclusion"] if v else \
            ("on file" if r["validated"] else "")
        e["validation_date"] = v["date"] if v else None
        if v:
            e["validated"] = v["validated"]
        e["materiality_cents"] = materiality_cents(con, r["size"], ecl)
        e["evidence_n"] = evidence(con, r["evidence"])
        e["level"] = materiality_level(r["use"], e["materiality_cents"])
        e["elevated"] = bool(r["judgement"]) \
            if r["evidence"] == "components" \
            else elevated(e["evidence_n"], r["judgement"])
        live = r["status"] not in ("not adopted",)
        e["own_tier"] = own_tier(e["level"], e["elevated"]) \
            if live else None
        rows.append(e)
    own = {e["id"]: e["own_tier"] for e in rows}
    final = inherit(own, {e["id"]: e["inputs"] for e in rows})
    users = {e["id"]: [] for e in rows}
    for e in rows:
        for i in e["inputs"]:
            users[i].append(e["id"])
    for e in rows:
        e["tier"] = final[e["id"]]
        e["used_by"] = sorted(users[e["id"]])
        e["due"] = _due(e["validated"], e["tier"], e["status"],
                        e["conclusion"])
    return rows


def save_inventory(inv: list[dict], path: Path = OUT) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    f = path / "inventory.json"
    f.write_text(json.dumps({"as_of": str(AS_OF), "models": inv},
                            indent=1) + "\n")
    return f


def load_inventory(path: Path = OUT) -> list[dict]:
    return json.loads((path / "inventory.json").read_text())["models"]


OWNER_SHORT = {"head of retail credit": "retail cr",
               "head of retail lending": "retail lend",
               "head of small-business lending": "small bus",
               "chief credit officer": "CCO",
               "head of credit risk": "credit risk",
               "chief financial officer": "CFO",
               "head of collections": "collections",
               "treasurer": "treasurer"}


def money(cents: int | None) -> str:
    """Millions of dollars for a register column."""
    if cents is None:
        return "-"
    return f"{cents / 1e8:,.0f}" if cents >= 1e10 else \
        f"{cents / 1e8:,.1f}"


def register_lines(inv: list[dict]) -> list[str]:
    """The register as printed: one model a line, at most 68 wide."""
    out = [f"{'id':<6}{'model':<26}{'owner':<12}{'$m':>6}"
           f"{'tier':>5} {'last':>4} {'due':>7}", "-" * 67]
    for e in inv:
        t = "-" if e["tier"] is None else str(e["tier"])
        out.append(f"{e['id']:<6}{e['name']:<26}"
                   f"{OWNER_SHORT[e['owner']]:<12}"
                   f"{money(e['materiality_cents']):>6}{t:>5} "
                   f"{(e['validated'] or '-'):>4} {e['due']:>7}")
    return out


# ------------------------------------ what the artefacts can prove

def check_artefacts(inv: list[dict], root: Path) -> list[dict]:
    """For each model: its saved files exist and read, and what they
    say agrees with the register and the policy file."""
    from ballast.config import ROOT  # noqa: F401  (root is passed in)
    policy = json.loads((BALLAST / "decision" /
                         "policy.json").read_text())
    out = []
    for e in inv:
        found, problems = 0, []
        for a in e["artefacts"]:
            p = root / a
            if not p.exists():
                problems.append(f"missing {a}")
                continue
            found += 1
            if p.suffix == ".json":
                d = json.loads(p.read_text())
                note = d.get("note", "") if isinstance(d, dict) else ""
                if "not in use" in note and e["status"] in LIVE:
                    problems.append(f"{p.name} says 'not in use'")
        if not e["artefacts"]:
            problems.append("nothing on file in Ballast")
        elif not any(a.startswith("data/") for a in e["artefacts"]):
            problems.append("in code only: no saved parameters")
        if e["id"] == "MK2R" and policy["champion"] != "Mark II-R":
            problems.append("policy names another champion")
        out.append({"id": e["id"], "files": len(e["artefacts"]),
                    "found": found, "problems": problems})
    return out


# --------------------------------------------- writing a model down
# The template every model document follows, with where each part
# comes from: "auto" parts Ballast fills from what it saved; "owner"
# parts need the people who built and approved the model.
DOC_TEMPLATE = [
    ("Identity and ownership", "auto"),
    ("Purpose, use and limits of use", "auto"),
    ("Status, approval and history", "owner"),
    ("Data and sample", "auto"),
    ("Method", "auto"),
    ("The model itself", "auto"),
    ("Performance", "auto"),
    ("Calibration and use as a probability", "auto"),
    ("Where its output goes", "auto"),
    ("Limitations and findings", "auto"),
    ("Monitoring", "auto"),
    ("Design choices and why", "owner"),
    ("Independent validation", "validator"),
]


def _mk2r_sections(e: dict, inv: list[dict]) -> dict[str, list[str]]:
    from ballast.scorecard import reject
    d = json.loads((BALLAST / "reject" /
                    "mark2_retro_ws.json").read_text())
    pol = json.loads((BALLAST / "decision" / "policy.json").read_text())
    smp = json.loads((BALLAST / "mark2" / "sample.json").read_text())
    pri = json.loads((BALLAST / "pricing" / "pricing.json").read_text())
    cal = json.loads((BALLAST / "parameters" /
                      "pd_calibration.json").read_text())
    card = reject.load_refit(d["name"]).scorecard()
    lines = card.table.groupby("characteristic", sort=False)["points"]
    top = int(card.base + lines.max().sum())
    pack = (BALLAST / "monitoring" / "pack_2025-12.txt").read_text()
    s: dict[str, list[str]] = {}
    s["Identity and ownership"] = [
        f"{e['name']} ({e['id']}); owner: {e['owner']}; developer: "
        f"{e['developer']}; tier {e['tier']}."]
    s["Purpose, use and limits of use"] = [
        f"Purpose: {e['purpose']}.", f"Not for: {e['not_for']}."]
    s["Data and sample"] = [
        f"Booked {smp['product']} loans applied for "
        f"{smp['development'][0]} to {smp['development'][1]}, bad = "
        f"{smp['bad']}, window {smp['window']}; plus bureau-retro "
        f"outcomes for applicants Fernhill did not lend to; "
        f"{d['rows_weighted']:,.0f} weighted rows, bad share "
        f"{d['bad_share']:.2%}. Out of time: "
        f"{smp['out_of_time'][0]} to {smp['out_of_time'][1]}."]
    s["Method"] = [
        f"Weight-of-evidence logistic regression on "
        f"{len(card.characteristics)} characteristics with Mark II's "
        f"bins; points scaled 600 = 50:1, 20 to double the odds."]
    s["The model itself"] = [
        f"Base {card.base}, highest score {top}; lines: "
        + ", ".join(card.characteristics) + "."]
    s["Performance"] = []          # nothing saved beside the model
    s["Calibration and use as a probability"] = [
        f"The scale is not a PD. First-year PD = 1 / (1 + exp(-("
        f"{cal['a']:.3f} {cal['b']:+.4f} x score))), "
        f"method {cal['method']}."]
    s["Where its output goes"] = [
        f"Cut-off {pol['cutoff']}, refer band "
        f"{pol['cutoff'] - pol['refer_below']}-"
        f"{pol['cutoff'] + pol['refer_above'] - 1}; price tiers start "
        f"at {', '.join(str(x) for x in pri['grid']['edges'])}; "
        f"used by {', '.join(e['used_by'])}."]
    s["Limitations and findings"] = [
        f"{f['id']} {f['severity']}, {f['status']}: {f['issue']}"
        for f in FINDINGS if f["model"] == e["id"]]
    mon = []
    for ln in pack.splitlines():
        t = ln.split()
        if ln.startswith("personal, Mark II-R"):
            mon.append(f"December 2025: {t[3]} applicants, mean "
                       f"{t[4]}, shift {t[5]}, PSI {t[6]} against "
                       f"January 2023 to June 2024 (noise {t[8]}).")
        elif "Mark II-R promise" in ln:
            mon.append("Alert: " + ln.split(".", 1)[1].strip() + ".")
        elif ln.startswith("Gini:") or "line that moved" in ln:
            mon.append(ln.strip() + ".")
    s["Monitoring"] = mon
    return s


def document(model_id: str, inv: list[dict]) -> tuple[str, dict]:
    """The model document as Markdown, and each section's state:
    'filled', 'empty' (Ballast saved nothing for it) or who must
    write it."""
    e = next(m for m in inv if m["id"] == model_id)
    if model_id != "MK2R":
        raise NotImplementedError("only Mark II-R is written so far")
    auto = _mk2r_sections(e, inv)
    md = [f"# {e['name']}: model document", "",
          f"As at {AS_OF:%d %B %Y}; generated by Ballast.", ""]
    state = {}
    for title, source in DOC_TEMPLATE:
        md += [f"## {title}", ""]
        if source == "validator" and e["validation_date"]:
            f = [x for x in validation_findings()
                 if x["model"] == model_id]
            md.append(f"- Validated {e['validation_date']}: "
                      f"{e['conclusion']}; findings "
                      + ", ".join(x["id"] for x in f) + ".")
            state[title] = "filled"
        elif source == "auto" and auto.get(title):
            md += [f"- {x}" for x in auto[title]]
            state[title] = "filled"
        elif source == "auto":
            md.append("- NOTHING SAVED: to be supplied before review.")
            state[title] = "empty"
        else:
            md.append(f"- To be written by the {source}.")
            state[title] = source
        md.append("")
    return "\n".join(md), state


# --------------------------------------------------- findings log
# Issues the book found, as Fernhill's validation and credit review
# functions would log them. Severity: high = could materially misstate
# a decision, a price, the provision or capital, or treat customers
# unfairly; medium = weakens the model in a known part of the book or
# rests on evidence too thin to confirm; low = records and housekeeping.
# Status: open; mitigated (a control covers it for now); accepted (the
# owner keeps the risk, watched); closed (fixed and checked).
SEVERITY = ("high", "medium", "low")
STATUS = ("open", "mitigated", "accepted", "closed")
FINDINGS = [dict(zip(("id", "model", "chapters", "severity", "status",
                      "issue"), f)) for f in [
    ("F01", "MK1", "5,11", "high", "open",
     "bureau line not re-set for version 3"),
    ("F02", "MK1", "24", "high", "closed",
     "alarm rule could not ring at volume"),
    ("F03", "MK1", "8,11", "high", "open",
     "no independent validation since 2015"),
    ("F04", "MK1", "29", "medium", "open",
     "mortgage use not in 2026 record"),
    ("F05", "MK2", "8", "medium", "closed",
     "wrong signs from shared no-file bin"),
    ("F06", "MK2", "9", "high", "closed",
     "no lead over Mark I on all scored"),
    ("F07", "MK2R", "11,18", "medium", "mitigated",
     "scale over-promises: it is not a PD"),
    ("F08", "MK2R", "13", "medium", "accepted",
     "over-predicts young borrowers' risk"),
    ("F09", "MK2R", "13,24", "high", "open",
     "women's 2025 approvals below parity"),
    ("F10", "MK2R", "29", "low", "open",
     "saved file still says 'not in use'"),
    ("F11", "MK2R", "29", "medium", "open",
     "performance not saved with the model"),
    ("F12", "CHAL", "10", "medium", "open",
     "scores move with seed and refits"),
    ("F13", "SME1", "16", "high", "open",
     "owner's bureau line not re-set"),
    ("F14", "SME1", "16", "medium", "open",
     "security line points the wrong way"),
    ("F15", "FRM", "16", "high", "open",
     "analysts hold grades the model moves"),
    ("F16", "RATE", "16,18", "medium", "accepted",
     "PDs of grades 1-6 unconfirmable"),
    ("F17", "PD12", "18", "medium", "open",
     "calibration light in band 540-559"),
    ("F18", "PD12", "18", "medium", "accepted",
     "economy effect from one recession"),
    ("F19", "LGD", "19", "medium", "closed",
     "recent workouts read as finished"),
    ("F20", "LGD", "19,20", "medium", "open",
     "mortgage LGD from a benign decade"),
    ("F21", "CCF", "19", "medium", "accepted",
     "revolver CCF rests on 17 defaults"),
    ("F22", "ECL", "18,20", "high", "open",
     "commercial year-one PD unsettled"),
    ("F23", "ECL", "20", "medium", "mitigated",
     "mortgage payment shock missed"),
    ("F24", "PRICE", "12", "medium", "open",
     "capital and hurdle are assumptions"),
    ("F25", "SEC", "28", "medium", "open",
     "correlation assumed; no triggers"),
    ("F26", "CURE", "25", "low", "accepted",
     "2024 test too small for 3-month cure"),
    ("F27", "MK1", "4,9,29", "medium", "open",
     "low-side overrides at any depth"),
]]


# Findings that Chapter 23's validations recorded again, by their ids
# there: the same weakness, logged once, with both ids on the record.
SAME_AS = {"F07": "MK2R-2", "F08": "MK2R-4", "F09": "MK2R-3",
           "F15": "FRM-2", "F16": "RATE-1", "F17": "PD12-1",
           "F21": "CCF-2"}
for _f in FINDINGS:
    _f["same_as"] = SAME_AS.get(_f["id"], "")


def new_from_validation() -> list[dict]:
    """The validation reports' findings not already in FINDINGS, as
    log entries: each is open until the condition it sets is met."""
    seen = set(SAME_AS.values())
    return [{"id": f["id"], "model": f["model"], "chapters": "23",
             "severity": f["severity"], "status": "open",
             "issue": f["issue"], "blocks": f["blocks"], "same_as": ""}
            for f in validation_findings() if f["id"] not in seen]


def findings_table(findings=FINDINGS) -> pd.DataFrame:
    """Counts by severity and status."""
    f = pd.DataFrame(findings)
    t = pd.crosstab(pd.Categorical(f.severity, SEVERITY),
                    pd.Categorical(f.status, STATUS), dropna=False)
    t.index.name, t.columns.name = "severity", "status"
    return t


# ------------------------------------------ the three lines, who does
# Who does what at Fernhill. R: does it; A: answers for it (one A a
# row); C: must be asked first; I: is told.
ROLES = [("owners", 1, "retail lending, underwriters, branches, "
                        "relationship managers, collections"),
         ("build", 1, "credit risk modelling: build and run "
                      "models"),
         ("credit", 2, "chief credit officer, credit officers, "
                       "credit committee"),
         ("valid", 2, "model validation: independent of the "
                      "builders"),
         ("CRO", 2, "chief risk officer: model risk policy, the "
                    "inventory, reports to the board"),
         ("audit", 3, "internal audit: reports to the board's "
                      "audit committee")]
RACI = {
    "build or change a model": "C R I C A I",
    "own a model and its use": "A C C C I I",
    "validate a model": "I C I R A I",
    "approve a model for use": "C C C C A I",
    "monitor a model": "R R I C A I",
    "keep the model inventory": "I C I C A I",
    "override a score or grade": "R I A C I I",
    "approve commercial credit": "R I A I I I",
    "set credit policy": "C C R I A I",
    "audit the whole": "I I I I I A",
}


def raci_lines() -> list[str]:
    """The matrix as printed, at most 68 wide."""
    names = "".join(f"{r[0][:6]:>7}" for r in ROLES)
    lines = "".join(f"{r[1]:>7}" for r in ROLES)
    out = [f"{'':<26}{names}", f"{'line of defence':<26}{lines}",
           "-" * 68]
    for task, codes in RACI.items():
        out.append(f"{task:<26}" + "".join(f"{x:>7}"
                                           for x in codes.split()))
    return out


# ------------------------------------------- delegated authority
# Fernhill's lending authority for commercial credit. A level may
# approve a client's total exposure up to the smaller of its cap and
# its budget divided by the grade's PD: the budget is the exposure
# times PD (dollars expected to default in a year) that one signature
# may take on. The result is rounded down to a round amount; below
# MIN_AUTHORITY the level has none. Above every level: the board.
AUTHORITY = [("senior credit officer", 3_000_000, 1_000_000_000),
             ("chief credit officer", 9_000_000, 2_500_000_000),
             ("credit committee", 500_000_000, 10_000_000_000)]
BOARD = "board risk committee"
MIN_AUTHORITY_CENTS = 100_000_000
ROUND_STEPS = (1, 2, 2.5, 5, 7.5)


def round_down(cents: float) -> int:
    """The largest round amount (1, 2, 2.5, 5 or 7.5 times a power of
    ten dollars) at or below `cents`."""
    if cents <= 0:
        return 0
    k = 10 ** math.floor(math.log10(cents))
    best = max(s * k for s in ROUND_STEPS if s * k <= cents)
    return int(best)


def authority_limit(level: int, grade: int) -> int:
    """The most a level may approve at a grade, in cents."""
    _, budget, cap = AUTHORITY[level]
    lim = min(cap, round_down(budget / MASTER_SCALE[int(grade)]))
    return lim if lim >= MIN_AUTHORITY_CENTS else 0


def authority_matrix() -> pd.DataFrame:
    """Levels by grade, in cents."""
    return pd.DataFrame({g: [authority_limit(i, g)
                             for i in range(len(AUTHORITY))]
                         for g in MASTER_SCALE},
                        index=[a[0] for a in AUTHORITY])


def approver(exposure_cents: int, grade: int) -> str:
    """The lowest level that may approve this total exposure at this
    grade."""
    for i, (name, _, _) in enumerate(AUTHORITY):
        if exposure_cents <= authority_limit(i, grade):
            return name
    return BOARD


LEVELS = [a[0] for a in AUTHORITY] + [BOARD]


def client_exposures(con, month: dt.date) -> pd.DataFrame:
    """Each commercial client's total limits at a month end, with the
    grades given at the review that month."""
    return con.execute("""
        SELECT f.company_id, sum(m.limit_cents) AS exposure_cents,
               any_value(r.internal_grade)::INT AS grade,
               any_value(r.model_grade)::INT AS model_grade,
               any_value(r.analyst_override) AS held
        FROM facility_months m
        JOIN facilities f USING (facility_id)
        JOIN ratings r ON r.company_id = f.company_id
         AND r.rating_date = m.month
        WHERE m.month = ? AND r.internal_grade IS NOT NULL
        GROUP BY f.company_id ORDER BY f.company_id""",
                       [month]).df()


# --------------------------------------------------- overrides
# Fernhill's override policy from 2026: low-side overrides by branch
# managers only, recorded with a reason, no deeper than
# MAX_OVERRIDE_DEPTH points below the cut-off; each region's rate is
# reported monthly and reviewed when it stands out from the bank's by
# more than chance allows.
REFER = 10                     # Mark I's refer band, either side
MAX_OVERRIDE_DEPTH = 80        # points below the cut-off
DEPTH_BANDS = [(-10, "in the refer band"), (-40, "11-40 below"),
               (-80, "41-80 below"), (-10_000, "over 80 below")]


def scored_applications(con) -> pd.DataFrame:
    """Mark I applications the score and the people around it decided:
    passed the policy rules and the fraud check."""
    return con.execute(f"""
        SELECT app_id, app_date, product, channel, region,
               mark1_score - cutoff AS margin, override, outcome,
               account_id,
               CASE WHEN mark1_score - cutoff < -{REFER} THEN 'below'
                    WHEN mark1_score - cutoff < {REFER} THEN 'band'
                    ELSE 'above' END AS zone
        FROM applications
        WHERE product IN ('personal', 'card', 'auto')
          AND (decline_reason IS NULL OR decline_reason IN
               ('score_below_cutoff', 'credit_officer'))
        ORDER BY app_id""").df()


def first_year_bad(con) -> pd.DataFrame:
    """Booked accounts' worst missed payments in months on book 1-12
    (bad = three or more), for applications with a full year."""
    return con.execute("""
        SELECT a.account_id, max(p.missed) >= 3 AS bad
        FROM performance p JOIN accounts a USING (account_id)
        WHERE datediff('month', a.open_date, p.month) BETWEEN 1 AND 12
          AND a.open_date <= DATE '2024-12-31'
        GROUP BY a.account_id ORDER BY a.account_id""").df()


def depth_band(margin: pd.Series) -> pd.Series:
    out = pd.Series(DEPTH_BANDS[-1][1], index=margin.index)
    for lo, name in reversed(DEPTH_BANDS):
        out[margin >= lo] = name
    return out


def binomial_z(x: int, n: int, p: float) -> float:
    """How many standard errors x successes in n sit from rate p."""
    return (x - n * p) / math.sqrt(n * p * (1 - p)) if n else 0.0


def holds(rv: pd.DataFrame) -> pd.DataFrame:
    """Reviews where the model wanted a move, by year and direction:
    how many, how many held, and later defaults where known."""
    from ballast.commercial import rating as rt
    m = rt.moves(rv)
    m = m[m["wanted"] != 0].copy()
    m["direction"] = np.where(m["wanted"] > 0, "down", "up")
    m["year"] = pd.to_datetime(m["review_date"]).dt.year
    return m


# ------------------------------------------- the supervisor's visit
# The examination agenda Fernhill prepares against: each item and the
# evidence Ballast produces for it (see code/29/10_examination.py).
AGENDA = [
    ("1", "Model inventory and tiering"),
    ("2", "Validation coverage of material models"),
    ("3", "Findings and remediation"),
    ("4", "Retail scorecards: Mark I and Mark II-R"),
    ("5", "IFRS 9 provision: models and judgements"),
    ("6", "Commercial grading and overrides"),
    ("7", "Credit policy and delegated authority"),
    ("8", "Retail overrides"),
    ("9", "Fair lending and conduct"),
    ("10", "Monitoring and reporting to the board"),
]
