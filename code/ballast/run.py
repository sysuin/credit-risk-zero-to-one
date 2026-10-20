"""Ballast v1.0: Fernhill's credit risk function in one command.

    python -m ballast.run            # from the loan book (minutes)
    python -m ballast.run --check    # saved results only (seconds)
    make run                         # the same as the first

The run goes through Ballast in the order the book built it: the loan
book loaded and checked, the book's performance, the decision engine
over 2025's personal-loan applications, their prices, the risk
parameters, the provision on 31 December 2025, capital, the portfolio
loss distribution, the stress test, validation, monitoring, the model
inventory, the risk appetite statement and the risk committee pack for
January 2026.

Each step either reruns or reads saved results:

- **rerun**: computed again from the loan book and compared with the
  file its chapter saved, to the cent (or to the byte for text). The
  steps after it then read that file, which is now known to be what
  the loan book gives.
- **saved**: read from the chapter's file without recomputing, because
  recomputing is too slow to do on every run: the portfolio simulation
  of 200,000 years and its correlation estimates (Chapter 22) and the
  reverse stress search (Chapter 26); and the risk parameters and
  validations, which are estimates and judgements that a month-end run
  uses as approved rather than re-estimates.

Every step also sets its figures beside the ones its chapter printed,
found in that chapter's captured output, and the run ends with the
reconciliation table: step, value now, value in its chapter, equal.
`--check` skips every rerun and checks that each saved result exists
and still agrees with its chapter. The run writes only its report,
under data/ballast/run/. It never reads the truth.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from ballast.config import AS_OF, BALLAST, ROOT

OUT = BALLAST / "run"
WIDTH = 68
TOLERANCE_CENTS = 0.5      # a rerun equals its file within half a cent


# ------------------------------------------------------------ checks

@dataclass
class Check:
    """One figure: what the run makes it now, and what it is compared
    with. `chapter` is the chapter that printed `printed` in `source`
    (a captured output under code/), inside the words `context`;
    `chapter = 0` means the comparison is with a saved file, and
    `same` says whether the rerun and the file agree."""
    label: str
    now: str
    printed: str
    source: str
    chapter: int = 0
    same: bool | None = None
    context: str = "{}"

    def __post_init__(self):
        if self.same is not None:
            self.same = bool(self.same)        # numpy's bool too

    @property
    def equal(self) -> bool:
        if self.chapter == 0:
            return bool(self.same)
        return self.now == self.printed and self.found

    @property
    def found(self) -> bool:
        """The printed figure is still in the chapter's output."""
        if self.chapter == 0:
            return True
        f = ROOT / self.source
        words = self.context.format(*self.printed.split(", "))
        return f.exists() and words in f.read_text()


@dataclass
class Step:
    name: str
    chapters: str
    mode: str                         # "rerun" or "saved"
    checks: list[Check] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c.equal for c in self.checks)


@dataclass
class Report:
    steps: list[Step]
    rerun: bool

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    @property
    def checks(self) -> list[Check]:
        return [c for s in self.steps for c in s.checks]

    def summary(self) -> list[str]:
        """One line a step: what ran, how, and whether it agreed."""
        out = []
        for i, s in enumerate(self.steps, 1):
            n = len(s.checks)
            bad = sum(not c.equal for c in s.checks)
            verdict = "all equal" if not bad else f"{bad} DIFFER"
            word = "check" if n == 1 else "checks"
            out.append(f"{i:>2} {s.name:<12}{s.mode:<7}"
                       f"Ch {s.chapters:<8}{n:>2} {word}, {verdict}")
        k = sum(c.equal for c in self.checks)
        out.append(f"{k} of {len(self.checks)} figures equal")
        return out

    def table(self) -> list[str]:
        """The reconciliation table, no wider than the page."""
        out = [f"{'':<2}{'figure':<30}{'now':>15}{'in its chapter':>15}"
               f"{'':>2}="]
        for s in self.steps:
            out.append(f"{s.name.upper()}  ({s.mode}, Ch {s.chapters})")
            for c in s.checks:
                ref = c.printed if c.chapter else "file"
                mark = "yes" if c.equal else "NO"
                out.append(f"  {c.label:<30}{c.now:>15}{ref:>15}"
                           f"{'':>2}{mark:<4}".rstrip())
        wide = [x for x in out if len(x) > WIDTH]
        if wide:
            raise ValueError(f"table lines wider than {WIDTH}: {wide}")
        return out

    def to_json(self) -> dict:
        return {"as_of": str(AS_OF), "rerun": self.rerun, "ok": self.ok,
                "steps": [{**{k: v for k, v in asdict(s).items()
                              if k != "seconds"},
                           "ok": s.ok,
                           "checks": [{**asdict(c), "equal": c.equal}
                                      for c in s.checks]}
                          for s in self.steps]}


# --------------------------------------------------------- formatting

def n(x) -> str:
    return f"{int(x):,}"


def dollars(cents) -> str:
    return f"{cents / 100:,.0f}"


def usd(cents) -> str:
    return f"${cents / 100:,.0f}"


def millions(cents, d: int = 1, sign: str = "$") -> str:
    return f"{sign}{cents / 1e8:,.{d}f}m"


def pct(x, d: int = 1) -> str:
    return f"{x:.{d}%}"


def same_cents(a, b) -> bool:
    return abs(float(a) - float(b)) <= TOLERANCE_CENTS


def out(ch: int, name: str) -> str:
    """Where chapter `ch` keeps a listing's captured output."""
    return f"code/{ch:02d}/{name}.out"


# ------------------------------------------------------------ the steps
# Each takes the run's context (a read-only connection and whatever the
# earlier steps left) and whether to rerun, and returns its checks.

def data_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import data
    con = ctx["con"]
    if rerun:
        apps = data.load_applications(con)
        acc = data.load_accounts(con)
        perf = data.load_performance(con)
        data.check_links(apps, acc, perf)      # raises if any fails
        counts = len(apps), len(acc), len(perf)
        del perf
    else:
        counts = tuple(
            con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("applications", "accounts", "performance"))
    src = out(5, "15_load_properly")
    return [Check("applications, every check", n(counts[0]), "177,878",
                  src, 5),
            Check("accounts", n(counts[1]), "87,762", src, 5),
            Check("account-months", n(counts[2]), "2,487,898", src, 5)]


CHARGE_OFFS = """
    SELECT year(month) AS yr, sum(balance_cents) AS lost
    FROM performance
    WHERE product = 'personal' AND status = 'charged_off'
      AND year(month) IN (2024, 2025)
    GROUP BY yr ORDER BY yr"""


def performance_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import performance as perf
    con = ctx["con"]
    lost = dict(con.execute(CHARGE_OFFS).fetchall())
    eps = perf.default_episodes(con, "dod2021")
    r = perf.portfolio_rates(con, "personal", 2025, eps)
    src1 = out(1, "02_charge_offs")
    return [Check("personal charge-offs, 2024", dollars(lost[2024]),
                  "1,706,057", src1, 1),
            Check("personal charge-offs, 2025", dollars(lost[2025]),
                  "1,360,891", src1, 1),
            Check("personal default rate, 2025",
                  pct(r["default_rate"], 2), "2.43%",
                  out(6, "15_portfolio"), 6)]


def decision_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast.decision import policy as pol
    saved_f = pol.DECISION / "decisions_2025.parquet"
    saved = pd.read_parquet(saved_f)
    checks = []
    if rerun:
        from ballast import data
        from ballast.decision import engine
        raw = data.load_applications(ctx["con"], unknowns=False)
        apps = raw[raw["product"].astype(str).eq("personal")
                   & (raw["app_date"].astype(str) >= "2025-01-01")]
        p = pol.load_policy()
        d = engine.decide_all(apps, p, engine.load_champion(p))
        d = d.assign(reasons=d["reasons"].map("; ".join))
        d = d.reset_index(drop=True)
        same = d[saved.columns].equals(saved)
        checks.append(Check("decisions, rerun = saved file",
                            f"{len(d):,} rows", "", str(saved_f), 0,
                            same))
        ctx["apps_2025"] = apps
    else:
        d = saved
    ctx["decisions"] = d
    k = d.groupby("decision").size()
    k_stage = d.groupby(["decision", "stage"]).size()
    src = out(11, "16_ballast_decides")
    return checks + [
        Check("2025 applications decided", n(len(d)), "9,691", src, 11),
        Check("approved", n(k["approve"]), "5,120", src, 11),
        Check("referred to an underwriter", n(k["refer"]), "697", src,
              11),
        Check("declined at the rules",
              n(k_stage[("decline", "policy")]), "1,973", src, 11),
        Check("declined on the score",
              n(k_stage[("decline", "score")]), "1,901", src, 11)]


def pricing_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import pricing
    grid = pricing.load_pricing().grid
    d = ctx["decisions"]
    yes = d[d["decision"].isin(["approve", "refer"])].copy()
    yes["rate"] = grid.rate(yes["score"])
    quoted = ctx["con"].execute("""
        SELECT app_id, offered_rate_pct, price_test_arm
        FROM applications
        WHERE product = 'personal' AND app_date >= DATE '2025-01-01'
        ORDER BY app_id""").df()
    yes = yes.merge(quoted, on="app_id", how="left", validate="1:1")
    both = yes[yes["offered_rate_pct"].notna()
               & yes["price_test_arm"].isna()]
    src = out(12, "16_ballast_prices")
    return [Check("approved or referred, priced", n(len(yes)), "5,817",
                  src, 12),
            Check("Ballast's price, quoted ones",
                  f"{both['rate'].mean():.2f}%", "13.37%", src, 12)]


def parameters_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast.parameters import ead, lgd
    from ballast.parameters import pd as pdm
    H, L, E = pdm.load_hazards(), lgd.load(), ead.load()
    src = out(19, "17_parameters")
    return [Check("personal hazard, a point of u",
                  f"{H['personal'].default['u']:.3f}", "0.224",
                  out(18, "17_save_pd"), 18),
            Check("personal-loan LGD",
                  pct(L["products"]["personal"]["lgd"]), "65.1%", src,
                  19),
            Check("commercial revolver CCF",
                  f"{E['ccf']['revolver']:.2f}", "0.76", src, 19,
                  context="revolvers {}")]


def provision_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import ecl
    saved = ecl.load()
    checks = []
    if rerun:
        con = ctx["con"]
        params = ecl.parameters(con)
        r = ecl.run(con, ecl.AS_OF, params)
        cecl = ecl.run(con, ecl.AS_OF, params,
                       basis="cecl")["ecl"].sum()
        checks.append(Check("provision, rerun = saved file",
                            usd(r["ecl"].sum()), "", "data/ballast/ecl",
                            0, same_cents(r["ecl"].sum(),
                                          saved["ecl"].sum())))
        checks.append(Check("CECL, rerun = saved file", usd(cecl), "",
                            "data/ballast/ecl", 0,
                            same_cents(cecl, saved["cecl"].sum())))
        pl = r[(r["product"] == "personal") & (r["stage"] < 3)
               & (r["mob"] >= 1) & (r["missed"] <= 2)]
        checks.append(Check("personal 12-month PD, weighted",
                            pct(pl["pd12"].mean(), 2), "2.98%",
                            out(20, "10_run"), 20))
    else:
        r = saved
    return checks + [
        Check("provision, 31 Dec 2025", millions(r["ecl"].sum(), 2, ""),
              "231.20m", out(20, "16_save"), 20),
        Check("accounts and facilities", n(len(r)), "34,915",
              out(20, "16_save"), 20),
        Check("CECL alongside", millions(saved["cecl"].sum(), 2),
              "$289.67m", out(20, "16_save"), 20)]


def capital_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import capital
    saved = capital.load()
    checks = []
    if rerun:
        r = capital.run(ctx["con"])
        same = (same_cents(r.sa_rwa.sum(), saved.sa_rwa.sum())
                and same_cents(r.irb_rwa.sum(), saved.irb_rwa.sum()))
        checks.append(Check("RWA, rerun = saved file",
                            usd(r.irb_rwa.sum()), "",
                            "data/ballast/capital", 0, same))
    else:
        r = saved
    k = capital.bank_capital(ctx["con"])
    ratio = k["cet1"] / (r.sa_rwa.sum() + k["operational_rwa"]
                         + k["market_rwa"])
    src = out(21, "12_irb")
    return checks + [
        Check("credit RWA, standardised", usd(r.sa_rwa.sum()),
              "$5,402,435,086", src, 21),
        Check("credit RWA, IRB", usd(r.irb_rwa.sum()), "$5,320,552,984",
              src, 21),
        Check("CET1 ratio, standardised", pct(ratio), "16.7%",
              out(21, "17_ratios"), 21)]


def portfolio_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import portfolio as pf
    s = pf.load()
    src = out(22, "15_build")
    return [Check("expected loss, simulated", millions(s["el"]),
                  "$150.3m", src, 22),
            Check("loss in 1 year in 1,000",
                  millions(s["quantiles"]["0.999"]), "$970.4m", src,
                  22),
            Check("economic capital", millions(s["ec_999"]), "$820.1m",
                  src, 22)]


def stress_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import stress
    saved = stress.load()
    y = saved["years"]
    checks = []
    if rerun:
        con = ctx["con"]
        again = stress.project(stress.inputs(con),
                               stress.paths(con)["stress_2026"],
                               "stress_2026")["years"]
        old = y[y.scenario == "stress_2026"].reset_index(drop=True)
        cols = ["loss", "provision", "charge", "nii", "cet1"]
        diff = (again[cols] - old[cols]).abs().to_numpy().max()
        checks.append(Check("supervisor's, rerun = saved",
                            f"{diff:.2f} cents", "",
                            "data/ballast/stress", 0,
                            diff <= TOLERANCE_CENTS))
    s, rev = saved["summary"], saved["reverse"]
    src = out(26, "11_build")
    return checks + [
        Check("CET1 trough, severe", pct(s["trough_sa"]["severe"]),
              "9.7%", src, 26),
        Check("CET1 trough, supervisor's",
              pct(s["trough_sa"]["stress_2026"]), "-2.1%", src, 26),
        Check("reverse stress, saved",
              f"x {rev['stress_2026']['k']:.2f}", "x 0.51", src, 26)]


def validation_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import validation as vd
    r = pd.Series([x["conclusion"] for x in vd.load()]).value_counts()
    return [Check("approved with conditions, not",
                  f"{r.get('approved with conditions', 0)}, "
                  f"{r.get('not approved', 0)}", "5, 1",
                  out(29, "02_register"), 29,
                  context="{} approved with conditions, {} not")]


def monitoring_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import monitoring as mon
    saved_f = mon.MONITORING / f"pack_{AS_OF:%Y-%m}.txt"
    saved = saved_f.read_text()
    checks = []
    if rerun:
        text = mon.pack(ctx["con"])
        checks.append(Check("December pack, rerun = saved",
                            f"{len(text.splitlines())} lines", "",
                            str(saved_f), 0, text == saved))
    alerts = saved.split("FOR ATTENTION")[1].split("\n\n")[0].strip()
    psi = alerts.splitlines()[0].split("PSI ")[1].rstrip(")")
    return checks + [Check("card score PSI on 2016", psi, "0.082",
                           out(24, "15_monthly_pack"), 24,
                           context="(PSI {})"),
                     Check("alerts for attention",
                           n(len(alerts.splitlines())), "6",
                           out(29, "12_examination"), 29,
                           context="{} alerts for attention")]


def governance_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import governance as gv
    saved = gv.load_inventory()
    checks = []
    if rerun:
        inv = json.loads(json.dumps(gv.build_inventory(ctx["con"]),
                                    default=str))
        checks.append(Check("inventory, rerun = saved", n(len(inv)), "",
                            "data/ballast/governance", 0, inv == saved))
    live = sum(e["tier"] is not None for e in saved)
    return checks + [Check("models, live", f"{len(saved)}, {live}",
                           "21, 20", out(29, "02_register"), 29,
                           context="{} models, {} live")]


def appetite_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import appetite as ap
    saved = pd.DataFrame(ap.load()["statement"])
    checks = []
    if rerun:
        st = ap.statement(ap.position(ctx["con"]))
        same = (st["status"].tolist() == saved["status"].tolist()
                and np.allclose(st["value"], saved["value"]))
        checks.append(Check("statement, rerun = saved",
                            f"{len(st)} metrics", "", "data/ballast/"
                            "appetite", 0, same))
    else:
        st = saved
    k = st["status"].value_counts()
    return checks + [Check("green, amber, red",
                           f"{k.get('green', 0)}, {k.get('amber', 0)}, "
                           f"{k.get('red', 0)}", "4, 3, 7",
                           out(27, "08_statement"), 27,
                           context="{} green, {} amber, {} red")]


def pack_step(ctx: dict, rerun: bool) -> list[Check]:
    from ballast import report
    saved_f = report.OUT / "pack_2026-01.md"
    saved = saved_f.read_text()
    text = report.pack()
    return [Check("pack, written = saved", f"{len(text):,} bytes", "",
                  str(saved_f), 0, text == saved),
            Check("pack lines", f"{len(text.splitlines())}", "172",
                  out(27, "10_pack"), 27, context="{} lines")]


STEPS: list[tuple[str, str, str, Callable]] = [
    ("data", "5", "rerun", data_step),
    ("performance", "1, 6", "rerun", performance_step),
    ("decisions", "11", "rerun", decision_step),
    ("prices", "12", "rerun", pricing_step),
    ("parameters", "18, 19", "saved", parameters_step),
    ("provision", "20", "rerun", provision_step),
    ("capital", "21", "rerun", capital_step),
    ("portfolio", "22", "saved", portfolio_step),
    ("stress", "26", "rerun", stress_step),
    ("validation", "23, 29", "saved", validation_step),
    ("monitoring", "24, 29", "rerun", monitoring_step),
    ("governance", "29", "rerun", governance_step),
    ("appetite", "27", "rerun", appetite_step),
    ("pack", "27", "rerun", pack_step),
]


# --------------------------------------------------------------- run

def run(con=None, rerun: bool = True, steps=STEPS,
        log: Callable[[str], None] | None = None) -> Report:
    """Every step in order; with `rerun=False`, the check-only run."""
    import fernhill
    ctx = {"con": con or fernhill.connect()}
    done = []
    for name, chapters, mode, fn in steps:
        t0 = time.perf_counter()
        checks = fn(ctx, rerun and mode == "rerun")
        s = Step(name, chapters, mode if rerun else "check", checks,
                 time.perf_counter() - t0)
        done.append(s)
        if log:
            log(f"{len(done):>2} {name:<12}{s.mode:<7}"
                f"{s.seconds:>6.0f}s  {'ok' if s.ok else 'DIFFERS'}")
    return Report(done, rerun)


def save(report: Report) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"run_{AS_OF}.json"
    f.write_text(json.dumps(report.to_json(), indent=1) + "\n")
    return f


def load() -> dict:
    return json.loads((OUT / f"run_{AS_OF}.json").read_text())


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(prog="python -m ballast.run",
                                description=__doc__.splitlines()[0])
    a.add_argument("--check", action="store_true",
                   help="read saved results only and reconcile them")
    args = a.parse_args(argv)
    t0 = time.perf_counter()
    rep = run(rerun=not args.check, log=print)
    print()
    print("\n".join(rep.table()))
    if not args.check:
        print(f"\nreport: {save(rep).relative_to(ROOT)}")
    print(f"{sum(c.equal for c in rep.checks)} of {len(rep.checks)} "
          f"figures equal; {time.perf_counter() - t0:.0f} seconds")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
