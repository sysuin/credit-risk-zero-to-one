"""Fernhill's risk appetite: how much it will lose, and where (Chapter 27).

Everything here reads what earlier chapters saved: Fernhill's capital
and Chapter 21's capital run, Chapter 20's provision, Chapter 22's loss
distribution and each pool's and name's share of it, Chapter 26's
stress projections, and the governance files of Chapter 29. It derives
the 2026 risk appetite statement from that evidence, measures the bank
against it, sets limits from capital and from the stress test, and
measures the plan for the commercial book through the same stress. It
writes only under data/ballast/appetite/.

    pos = position(con)                 # every metric's value today
    st = statement(pos)                 # metrics, thresholds, RAG
    save(st, pos, extra)                # the statement for the pack
"""
from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np
import pandas as pd

from ballast import capital, ecl, stress
from ballast import monitoring as mon
from ballast import portfolio as pf
from ballast.config import AS_OF, BALLAST
from ballast.parameters import ead as eadm

OUT = BALLAST / "appetite"

# ------------------------------------------------- Fernhill's choices
HURDLE = 0.15            # pre-tax return asked of capital (Chapter 12)
BUFFER = 0.01            # management buffer above the stressed need
WATCHLIST = 9            # grades 9 and 10: Chapter 20's watchlist
NAME = (0.10, 0.15)      # one client's EAD, share of Tier 1
LARGE_EXPOSURE = 0.25    # the rules' limit, share of Tier 1
SECTOR = (0.20, 0.25)    # one sector, share of commercial EAD
REGION = (0.30, 0.35)    # one region, share of retail balances
COMMERCIAL = (0.70, 0.80)  # commercial share of drawn lending
CHARGE = (0.50, 0.75)    # base-case impairment charge / NII
TAIL = (1.00, 1.50)      # one-in-ten year's credit loss / NII
ARREARS = (0.75, 0.90)   # quantiles of 2017-2025's monthly arrears
MODELS = (0, 2)          # tier 1 models unvalidated; findings undated
MEETING = dt.date(2026, 1, 8)   # the board risk committee, January
BANDS = {"grades 1-5": (1, 5), "grades 6-8": (6, 8),
         "grades 9-10": (9, 10)}
RETAIL = ("personal", "card", "auto", "mortgage", "sme_term",
          "sme_overdraft", "sme_emergency")


# ------------------------------------------------------ what is held

def market(con) -> dict:
    """The policy rate and Fernhill's cost of funds on AS_OF (%)."""
    p, c = con.execute("SELECT policy_rate_pct, cost_of_funds_pct "
                       "FROM market_rates WHERE month = ?",
                       [AS_OF]).fetchone()
    return {"policy": float(p), "cof": float(c)}


def capital_now(con) -> dict:
    """Fernhill's capital, standardised RWA and CET1 ratio on AS_OF,
    with the requirement (minimum plus buffers) and the minimum."""
    k = capital.bank_capital(con)
    r = capital.load()
    sa = float(r.sa_rwa.sum()) + k["operational_rwa"] + k["market_rwa"]
    return {**{x: float(v) for x, v in k.items()},
            "tier1": float(k["cet1"] + k["at1"]), "sa_rwa": sa,
            "cet1_ratio": k["cet1"] / sa,
            "requirement": capital.requirements()["cet1"],
            "minimum": capital.MINIMUM["cet1"]}


def losses() -> pd.DataFrame:
    """How much Fernhill could lose, measured every way Ballast has
    measured it: the year's expected loss, the provision held, the
    one-year distribution's quantiles and expected shortfall (Chapter
    22), and three years of each stress (Chapter 26), with the CET1
    each stress uses up to its lowest point (cents)."""
    lo, s = pf.load(), stress.load()
    q, y = lo["quantiles"], s["years"]
    z = s["summary"]["year_zero"]
    rows = [("expected loss, one year", lo["el"], np.nan),
            ("provision held", float(ecl.load().ecl.sum()), np.nan),
            ("1 year in 10", q["0.9"], np.nan),
            ("1 year in 100", q["0.99"], np.nan),
            ("1 year in 1,000", q["0.999"], np.nan),
            ("beyond 1 in 1,000, average", lo["es"]["0.999"], np.nan)]
    for name, label in (("base", "base, three years"),
                        ("severe", "severe, three years"),
                        ("stress_2026", "supervisor's, three years")):
        g = y[y.scenario == name]
        rows.append((label, float(g.loss.sum()),
                     z["cet1"] - float(g.cet1.min())))
    return pd.DataFrame(rows, columns=["measure", "loss", "cet1_used"])


# --------------------------------------------------------- capital

def capital_target(cap: dict, summary: dict, buffer: float = BUFFER
                   ) -> dict:
    """The CET1 ratio Fernhill should hold, from its stress tests.

    Each scenario's depletion is the fall from today's ratio to its
    trough (the standardised RWA of a static book do not move, so a
    fall in points is a fall in dollars). The ratio needed to come
    through a scenario is the line it must not cross plus that
    depletion. Fernhill's target is its requirement plus the depletion
    of its own severe scenario plus a management buffer; its tolerance
    is the CET1 minimum, without buffers, plus the same depletion: the
    ratio below which a repeat of its own severe scenario would take
    it under the minimum itself."""
    start = summary["year_zero"]["cet1_sa"]
    drop = {k: start - v for k, v in summary["trough_sa"].items()}
    up = lambda x: math.ceil(round(x * 1000, 6)) / 1000  # noqa: E731
    return {"start": start, "drop": drop,
            "need": {k: cap["requirement"] + d for k, d in drop.items()},
            "target": up(cap["requirement"] + drop["severe"] + buffer),
            "tolerance": up(cap["minimum"] + drop["severe"]),
            "capacity": cap["requirement"]}


def ec_ceiling(cap: dict) -> float:
    """The largest economic capital, as a share of CET1, that leaves
    Fernhill at its CET1 minimum after its own one-in-a-thousand year."""
    return (cap["cet1"] - cap["minimum"] * cap["sa_rwa"]) / cap["cet1"]


# ------------------------------------------------ allocation, returns

def allocate(contrib: pd.DataFrame, ec: float) -> pd.DataFrame:
    """Each pool's and name's economic capital: its share of the
    expected shortfall beyond its own expected loss, scaled so that the
    shares add up to the book's economic capital (Euler allocation of
    expected shortfall, rescaled to VaR less EL)."""
    c = contrib.copy()
    k = ec / float((c.es_999 - c.el).sum())
    c["ec"] = (c.es_999 - c.el) * k
    return c


def band_of(grade) -> pd.Series:
    g = pd.Series(grade, dtype=float)
    out = pd.Series("", index=g.index, dtype=object)
    for b, (lo, hi) in BANDS.items():
        out[(g >= lo) & (g <= hi)] = b
    return out


def grades(r: pd.DataFrame | None = None) -> pd.Series:
    """Each commercial client's grade on AS_OF (Chapter 21's run)."""
    r = capital.load() if r is None else r
    com = r[r.segment == "commercial"]
    return com.groupby("company_id")["grade"].first().astype(int)


def segment_frame(e: pd.DataFrame, r: pd.DataFrame,
                  contrib: pd.DataFrame, by: str = "band") -> dict:
    """The provision run, the capital run and the contributions keyed
    by one segment column: retail products, and commercial clients by
    grade band (`by="band"`) or by grade (`by="grade"`)."""
    g = grades(r)
    key = band_of(g) if by == "band" else g.map(lambda x: f"grade {x}")
    key.index = g.index
    e = e.assign(seg=np.where(e.segment == "retail", e["product"],
                              e.account_id.str[:5].map(key)))
    r = r.assign(seg=np.where(r.segment == "retail", r["product"],
                              r.company_id.map(key)))
    c = contrib.assign(seg=np.where(contrib.kind == "pool",
                                    contrib.segment,
                                    contrib.id.map(key)))
    return {"e": e, "r": r, "c": c}


def returns(con, by: str = "band", target: float | None = None,
            hurdle: float = HURDLE) -> pd.DataFrame:
    """A year's return on capital by segment, before running costs.

    Income is each performing account's balance times its rate
    (Fernhill records no fees); funding is the balance at the cost of
    funds; the expected loss and the expected shortfall are Chapter
    22's; economic capital is allocated by `allocate`; regulatory
    capital is the standardised RWA at the target CET1 ratio. A segment
    is charged the larger of the two, because the bank must hold its
    regulatory capital whatever its own model says, and its own model
    where that says more. The capital earns the cost of funds it saves.
    `room` is what is left for running costs at the hurdle (cents)."""
    mk = market(con)
    lo = pf.load()
    if target is None:
        target = capital_target(capital_now(con),
                                stress.load()["summary"])["target"]
    c = allocate(pf.load_contributions(), lo["ec_999"])
    f = segment_frame(ecl.load(), capital.load(), c, by)
    e, r, c = f["e"], f["r"], f["c"]
    perf_ = e[e.stage < 3]
    t = pd.DataFrame({
        "drawn": e.groupby("seg").balance_cents.sum(),
        "income": (perf_.balance_cents * perf_.rate_pct / 100)
        .groupby(perf_.seg).sum(),
        "el": c.groupby("seg").el.sum(),
        "ec": c.groupby("seg").ec.sum(),
        "sa_rwa": r.groupby("seg").sa_rwa.sum()}).fillna(0.0)
    t["funding"] = t.drawn * mk["cof"] / 100
    t["reg"] = t.sa_rwa * target
    t["capital"] = t[["ec", "reg"]].max(axis=1)
    t["ret"] = t.income - t.funding - t.el + t.capital * mk["cof"] / 100
    t["roc"] = t.ret / t.capital
    t["room"] = t.ret - hurdle * t.capital
    order = [p for p in RETAIL if p in t.index] + \
        sorted(i for i in t.index if i not in RETAIL)
    return t.loc[order]


def total(t: pd.DataFrame, rows) -> pd.Series:
    """The sum of some segments of a `returns` table, its return on
    capital recomputed."""
    s = t.loc[list(rows)].sum()
    s["roc"] = s.ret / s.capital
    return s


def margins(con, t: pd.DataFrame, hurdle: float = HURDLE
            ) -> pd.DataFrame:
    """For commercial segments of a `returns` table: the margin over
    the policy rate each earns on what is drawn today, and the margin
    that would earn the hurdle on its capital before running costs
    (basis points)."""
    mk = market(con)
    com = t[~t.index.isin(RETAIL)].copy()
    now = com.income / com.drawn * 100 - mk["policy"]
    need = (mk["cof"] + (com.el + (hurdle - mk["cof"] / 100)
                         * com.capital) / com.drawn * 100
            - mk["policy"])
    return pd.DataFrame({"drawn": com.drawn, "now_bps": now * 100,
                         "need_bps": need * 100,
                         "gap_bps": (need - now) * 100})


# --------------------------------------------------- concentrations

def names(con, tier1: float, r: pd.DataFrame | None = None
          ) -> pd.DataFrame:
    """Each commercial client: grade, sector, EAD with Fernhill's own
    revolver conversion factor (Chapter 19) and with the standardised
    one, each as a share of Tier 1; largest first."""
    r = capital.load() if r is None else r
    com = r[(r.segment == "commercial") & ~r.in_default.astype(bool)]
    com = com.assign(ead=capital.irb_ead(
        com, revolver_ccf=eadm.load()["ccf"]["revolver"]))
    n = com.groupby("company_id").agg(
        grade=("grade", "first"), ead=("ead", "sum"),
        sa_ead=("sa_ead", "sum"), drawn=("drawn_cents", "sum"),
        limit=("limit_cents", "sum")).reset_index()
    info = con.execute("SELECT company_id, name, sector FROM companies"
                       ).df().set_index("company_id")
    n["name"] = n.company_id.map(info["name"])
    n["sector"] = n.company_id.map(info["sector"])
    n["share"] = n.ead / tier1
    n["sa_share"] = n.sa_ead / tier1
    n["grade"] = n.grade.astype(int)
    return (n.sort_values(["ead", "company_id"], ascending=[False, True])
            .reset_index(drop=True))


def sectors(n: pd.DataFrame) -> pd.Series:
    s = n.groupby("sector").ead.sum()
    return (s / s.sum()).sort_values(ascending=False)


def regions(con) -> pd.Series:
    """Each region's share of retail and small-business balances."""
    e = ecl.load()
    e = e[e.segment == "retail"]
    reg = con.execute("SELECT account_id, region FROM accounts").df()
    e = e.merge(reg, on="account_id", how="left")
    s = e.groupby("region").balance_cents.sum()
    return (s / s.sum()).sort_values(ascending=False)


def arrears(con) -> pd.Series:
    """Consumer accounts 30+ days behind, month by month (Chapter 24's
    measure), from January 2017, when the book had a year's history."""
    s = mon.stress_indicators(con, dt.date(2017, 1, 31), AS_OF)
    return s.set_index("month")["dq30"]


# ----------------------------------------------------- model risk

def model_risk(meeting: dt.date = MEETING) -> dict:
    """What the governance files say on the meeting's date: tier 1
    models in use without an independent validation dated on or before
    it, and the open high findings logged by then (the validators'
    own findings arrive with their reports, dated after it)."""
    inv = json.loads((BALLAST / "governance" / "inventory.json")
                     .read_text())["models"]
    fnd = json.loads((BALLAST / "governance" / "findings.json")
                     .read_text())
    dated = {m["id"]: m.get("validation_date") for m in inv}
    unval = [m["id"] for m in inv
             if m["tier"] == 1 and m["status"] == "in use"
             and not (dated[m["id"]]
                      and dated[m["id"]] <= meeting.isoformat())]
    logged = [f for f in fnd if f["chapters"] != "23"]
    high = [f for f in logged
            if f["severity"] == "high" and f["status"] == "open"]
    return {"unvalidated": unval, "open_high": high,
            "logged": len(logged), "undated": len(high)}


# ------------------------------------------------------ the statement

# id, area, metric, unit, higher is better, owner, basis
METRICS = [
    ("C1", "capital", "CET1 ratio (standardised)", "pct", True,
     "CFO", "requirement + severe depletion + buffer"),
    ("C2", "capital", "CET1 trough, supervisor's", "pct", True,
     "CRO", "requirement; minimum"),
    ("C3", "capital", "economic capital / CET1", "pct", False,
     "CRO", "minimum after a 1-in-1,000 year; solvency"),
    ("E1", "earnings", "base-case charge / NII", "pct", False,
     "CFO", "costs at half of NII (placeholder)"),
    ("E2", "earnings", "1-in-10 credit loss / NII", "pct", False,
     "CFO", "judgement"),
    ("Q1", "quality", "watchlist EAD, grades 9-10", "usd", False,
     "CCO", "supervisor's trough at 8.0% / 4.5%"),
    ("Q2", "quality", "consumer arrears, 30+ days", "pct", False,
     "retail", "2017-25 months: 75th / 90th pct"),
    ("Q3", "quality", "commercial return, pre-cost", "pct", True,
     "CCO", "hurdle; zero"),
    ("N1", "concentration", "largest client / Tier 1", "pct", False,
     "CCO", "1 point of CET1 a default; judgement"),
    ("N2", "concentration", "largest sector / commercial", "pct", False,
     "CCO", "judgement (backstop)"),
    ("N3", "concentration", "largest region / retail", "pct", False,
     "retail", "judgement (backstop)"),
    ("N4", "concentration", "commercial / all lending", "pct", False,
     "CEO", "strategy"),
    ("M1", "models", "tier 1 models unvalidated", "n", False,
     "CRO", "model risk policy"),
    ("M2", "models", "open high findings, undated", "n", False,
     "CRO", "model risk policy"),
]


def rag(value: float, appetite: float, tolerance: float,
        higher: bool = True) -> str:
    """Green inside the appetite, amber beyond it but inside the
    tolerance, red beyond the tolerance."""
    if higher:
        return ("green" if value >= appetite
                else "amber" if value >= tolerance else "red")
    return ("green" if value <= appetite
            else "amber" if value <= tolerance else "red")


def position(con, watchlist_limits: dict | None = None) -> dict:
    """Every metric's value on AS_OF and every threshold that is
    derived rather than chosen, from the saved results. The watchlist
    limits come from `watchlist_limit` (saved by `save_limits`)."""
    cap = capital_now(con)
    s = stress.load()
    summ, y = s["summary"], s["years"]
    tgt = capital_target(cap, summ)
    lo = pf.load()
    base26 = y[(y.scenario == "base") & (y.year == 2026)].iloc[0]
    nii = summ["year_zero"]["nii"]
    t = returns(con, target=tgt["target"])
    com = total(t, [i for i in t.index if i not in RETAIL])
    n = names(con, cap["tier1"])
    e = ecl.load()
    ar = arrears(con)
    mr = model_risk()
    wl = watchlist_limits or load_limits()
    v = {"C1": cap["cet1_ratio"],
         "C2": summ["trough_sa"]["stress_2026"],
         "C3": lo["ec_999"] / cap["cet1"],
         "E1": base26.charge / base26.nii,
         "E2": lo["quantiles"]["0.9"] / nii,
         "Q1": float(n.ead[n.grade >= WATCHLIST].sum()),
         "Q2": float(ar.iloc[-1]),
         "Q3": float(com.roc),
         "N1": float(n.share.max()),
         "N2": float(sectors(n).iloc[0]),
         "N3": float(regions(con).iloc[0]),
         "N4": float(e[e.segment == "commercial"].balance_cents.sum()
                     / e.balance_cents.sum()),
         "M1": float(len(mr["unvalidated"])),
         "M2": float(mr["undated"])}
    th = {"C1": (tgt["target"], tgt["tolerance"]),
          "C2": (cap["requirement"], cap["minimum"]),
          "C3": (ec_ceiling(cap), 1.0),
          "E1": CHARGE, "E2": TAIL,
          "Q1": (wl["appetite"], wl["tolerance"]),
          "Q2": tuple(float(ar.quantile(q)) for q in ARREARS),
          "Q3": (HURDLE, 0.0), "N1": NAME, "N2": SECTOR, "N3": REGION,
          "N4": COMMERCIAL, "M1": MODELS, "M2": MODELS}
    return {"values": v, "thresholds": th, "capital": cap,
            "target": tgt, "returns": t, "names": n, "model_risk": mr,
            "watchlist": wl}


def statement(pos: dict) -> pd.DataFrame:
    """The 2026 statement: each metric with its appetite, tolerance,
    value today and status."""
    rows = []
    for mid, area, label, unit, higher, owner, basis in METRICS:
        a, t = pos["thresholds"][mid]
        val = pos["values"][mid]
        rows.append({"id": mid, "area": area, "metric": label,
                     "unit": unit, "higher": higher, "owner": owner,
                     "basis": basis, "appetite": a, "tolerance": t,
                     "value": val,
                     "status": rag(val, a, t, higher)})
    return pd.DataFrame(rows)


def fmt(value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value:.1%}"
    if unit == "usd":
        return f"${value / 1e8:,.0f}m"
    return f"{value:.0f}"


# ------------------------------------------- the stress, reshaped

def reshape(inp: dict, drawn: pd.Series | None = None,
            headroom: pd.Series | None = None,
            margin_bps: pd.Series | None = None) -> dict:
    """A copy of Chapter 26's stress inputs with commercial facilities
    changed: each facility's drawn amount times `drawn` (by facility
    id; 1 where absent), its undrawn headroom times `drawn` and then
    `headroom`, and its margin raised by `margin_bps`. The capital run
    and the opening provision follow the new book; CET1 does not move
    (a share sold at its carrying value, net of its provision)."""
    drawn = pd.Series(dtype=float) if drawn is None else drawn
    headroom = pd.Series(dtype=float) if headroom is None else headroom
    margin_bps = (pd.Series(dtype=float) if margin_bps is None
                  else margin_bps)

    def resize(df, dcol, lcol):
        df = df.copy()
        fd = df.account_id.map(drawn).fillna(1.0).to_numpy(float)
        fh = df.account_id.map(headroom).fillna(1.0).to_numpy(float)
        d = df[dcol].to_numpy(float)
        head = np.maximum(df[lcol].to_numpy(float) - d, 0)
        nd = d * fd
        df[dcol] = np.round(nd).astype("int64")
        df[lcol] = np.round(nd + head * fd * fh).astype("int64")
        if "rate_pct" in df:
            df["rate_pct"] = df.rate_pct + df.account_id.map(
                margin_bps).fillna(0.0) / 100
        return df

    out = dict(inp)
    out["cb"] = resize(inp["cb"], "balance_cents", "limit_cents")
    out["book"] = resize(inp["book"], "balance_cents", "limit_cents")
    cap = resize(inp["capital"], "drawn_cents", "limit_cents")
    com = (cap.segment == "commercial").to_numpy()
    rev = (cap["product"] == "commercial_revolver").to_numpy()
    und = np.where(rev, cap.limit_cents - cap.drawn_cents, 0)
    cap["undrawn_cents"] = np.where(com, und, cap.undrawn_cents)
    cap["sa_ead"] = np.where(com, cap.drawn_cents + cap.sa_ccf
                             * cap.undrawn_cents, cap.sa_ead)
    cap["sa_rwa"] = np.where(com, cap.sa_ead * cap.sa_rw, cap.sa_rwa)
    out["capital"] = cap
    out["prov0"] = stress.provision(out, None)["total"]
    return out


def watchlist_ids(inp: dict) -> pd.Index:
    cb = inp["cb"]
    return pd.Index(cb.account_id[cb.grade >= WATCHLIST])


def watchlist_limit(inp: dict, path: pd.DataFrame, today: float,
                    targets: dict, tol: float = 0.001,
                    steps: int = 6) -> dict:
    """The share of today's watchlist exposure (grades 9 and 10) at
    which the supervisor's scenario leaves the CET1 trough exactly at
    each target, everything else held as it is today. `today` is the
    trough as the book stands (Chapter 26's saved answer). The search
    is by false position (Illinois) between none of the watchlist and
    all of it, sharing every projection between the targets."""
    ids = watchlist_ids(inp)
    seen = {1.0: today}

    def trough(k):
        k = round(float(k), 6)
        if k not in seen:
            new = reshape(inp, drawn=pd.Series(k, index=ids))
            seen[k] = stress.project(new, path)["trough_sa"]
        return seen[k]

    trough(0.0)
    out = {}
    for name, goal in targets.items():
        a, b = 0.0, 1.0
        fa, fb = trough(a) - goal, trough(b) - goal
        side = 0
        for _ in range(steps):
            k = b - fb * (b - a) / (fb - fa)
            fk = trough(k) - goal
            if abs(fk) < tol:
                break
            if fk * fb < 0:
                a, fa = b, fb
                side = 0
            else:
                fa = fa / 2 if side == 1 else fa
                side = 1
            b, fb = k, fk
        out[name] = {"share": k, "trough": fk + goal}
    out["tried"] = {str(k): v for k, v in sorted(seen.items())}
    return out


def company_ead(cb: pd.DataFrame, ccf: float | None = None) -> pd.Series:
    """Each client's EAD from a facilities frame (Fernhill's own
    revolver conversion factor)."""
    ccf = eadm.load()["ccf"]["revolver"] if ccf is None else ccf
    head = (cb.limit_cents - cb.balance_cents).clip(lower=0)
    e = np.where(cb.kind == "revolver", cb.balance_cents + ccf * head,
                 cb.balance_cents)
    return pd.Series(e, index=cb.index).groupby(cb.company_id).sum()


def plan_steps(inp: dict, tier1: float, gap_bps: dict,
               watch_limit: float | None = None) -> list:
    """The commercial plan as cumulative changes to the book, each a
    (label, drawn, headroom, margin) of facility factors: 1 the
    watchlist's undrawn headroom cancelled; 2 its facilities that
    mature within twelve months not renewed; 3 every client above
    NAME[0] of Tier 1 brought down to it; 4 the grades in `gap_bps`
    repriced by that many basis points; and, given `watch_limit`
    (cents of EAD), 5 the rest of the watchlist run down to it."""
    cb = inp["cb"]
    watch = cb.grade >= WATCHLIST
    head = pd.Series(0.0, index=cb.account_id[watch
                                              & (cb.kind == "revolver")])
    gone = pd.Series(0.0, index=cb.account_id[watch
                                              & (cb.remaining <= 12)])
    after = cb.copy()
    after["limit_cents"] = np.where(after.account_id.isin(head.index),
                                    after.balance_cents,
                                    after.limit_cents)
    keep = ~after.account_id.isin(gone.index)
    e = company_ead(after[keep])
    cut = (NAME[0] * tier1 / e).clip(upper=1.0)
    names_f = pd.Series(cb.company_id.map(cut).fillna(1.0).to_numpy(),
                        index=cb.account_id)
    names_f = names_f[names_f < 1]
    drawn2 = pd.concat([gone, names_f[~names_f.index.isin(gone.index)]])
    price = pd.Series(cb.grade.map(gap_bps).fillna(0.0).to_numpy(),
                      index=cb.account_id)
    price = price[price > 0]
    out = [("watchlist headroom cancelled", None, head, None),
           ("watchlist maturities not renewed", gone, head, None),
           ("clients cut to 10% of Tier 1", drawn2, head, None),
           ("grades 5-8 repriced", drawn2, head, price)]
    if watch_limit is not None:
        rest = after[keep & watch]
        f = min(1.0, watch_limit / float(company_ead(rest).sum()))
        run = pd.Series(f, index=rest.account_id)
        drawn3 = drawn2.copy()
        both = drawn3.index.intersection(run.index)
        drawn3.loc[both] = drawn3.loc[both] * f
        drawn3 = pd.concat([drawn3, run[~run.index.isin(both)]])
        out.append(("watchlist down to its limit", drawn3, head, price))
    return out


# ------------------------------------------------------------ saving

def save_limits(limits: dict) -> str:
    """The watchlist limits found by `watchlist_limit` (cents)."""
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"limits_{AS_OF}.json"
    f.write_text(json.dumps(limits, indent=1, sort_keys=True) + "\n")
    return str(f.relative_to(BALLAST.parent.parent))


def load_limits() -> dict:
    return json.loads((OUT / f"limits_{AS_OF}.json").read_text())


def save(st: pd.DataFrame, pos: dict, extra: dict | None = None) -> str:
    """The statement, the position behind it and any extra results
    (the plan) for the risk committee pack."""
    OUT.mkdir(parents=True, exist_ok=True)
    n = pos["names"]
    t = pos["returns"]
    doc = {"as_of": str(AS_OF), "meeting": str(MEETING),
           "statement": st.to_dict(orient="records"),
           "capital": pos["capital"], "target": pos["target"],
           "names": n.head(10).to_dict(orient="records"),
           "names_over": int((n.share > NAME[0]).sum()),
           "sectors": sectors(n).to_dict(),
           "returns": t.reset_index(names="segment")
           .to_dict(orient="records"),
           "model_risk": {k: v for k, v in pos["model_risk"].items()},
           "watchlist": pos["watchlist"], **(extra or {})}
    f = OUT / f"appetite_{AS_OF}.json"
    f.write_text(json.dumps(doc, indent=1, sort_keys=True,
                            default=float) + "\n")
    return str(f.relative_to(BALLAST.parent.parent))


def load() -> dict:
    """The saved statement, with the measured plan if it is saved."""
    doc = json.loads((OUT / f"appetite_{AS_OF}.json").read_text())
    plan = OUT / f"plan_{AS_OF}.json"
    if plan.exists():
        doc["plan"] = json.loads(plan.read_text())
    return doc


def save_plan(plan: dict) -> str:
    """The plan measured through the stress test, for the pack."""
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"plan_{AS_OF}.json"
    f.write_text(json.dumps(plan, indent=1, sort_keys=True,
                            default=float) + "\n")
    return str(f.relative_to(BALLAST.parent.parent))
