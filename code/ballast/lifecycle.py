"""The lending lifecycle: which table each step writes; one life.

Every step in the life of a consumer or small-business loan leaves rows
in Fernhill's loan book. `STEPS` says which step writes which table, and
`life()` gathers every row an application left behind, from the form to
the last recovery. `print_life()` prints it in a page's width, so any
application can be read the way a credit officer reads a file.

    import fernhill
    from ballast.lifecycle import print_life
    print_life(fernhill.connect(), "A00000004")

Later chapters use it to look at the loans behind a number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import groupby


@dataclass(frozen=True)
class Step:
    """One step of the lifecycle and the table it leaves behind."""
    name: str
    table: str
    key: str            # the column that ties its rows to a loan
    columns: tuple      # the columns that record the step
    what: str


STEPS = (
    Step("apply", "applications", "app_id",
         ("app_date", "channel", "amount_requested_cents",
          "stated_income_cents", "bureau_score"),
         "what the applicant said and the bureau knew"),
    Step("check", "applications", "app_id",
         ("decline_reason",),
         "policy rules, affordability, fraud"),
    Step("decide", "applications", "app_id",
         ("mark1_score", "cutoff", "decision", "override"),
         "the score, the cut-off and the decision"),
    Step("offer", "applications", "app_id",
         ("offered_rate_pct", "offered_amount_cents", "outcome",
          "account_id"),
         "the offer, and whether it was taken"),
    Step("book", "accounts", "account_id",
         ("open_date", "amount_cents", "rate_pct", "payment_cents"),
         "the loan as written"),
    Step("service", "performance", "account_id",
         ("month", "balance_cents", "paid_cents", "missed",
          "status"),
         "every month end it is open"),
    Step("events", "account_events", "account_id",
         ("event_date", "event"),
         "payment holidays, bankruptcy, cures"),
    Step("collect", "collections", "account_id",
         ("month", "action"),
         "what collections did each month behind"),
    Step("default", "defaults", "account_id",
         ("default_month", "definition", "ead_cents"),
         "each default as it was recorded"),
    Step("close", "accounts", "account_id",
         ("close_date", "close_reason"),
         "repaid, prepaid, charged off, repossessed"),
    Step("recover", "recoveries", "account_id",
         ("month", "kind", "amount_cents"),
         "what came back after, and what it cost"),
)


@dataclass
class Life:
    """Everything one application left in the loan book."""
    app: dict
    accounts: list = field(default_factory=list)
    months: dict = field(default_factory=dict)       # account -> rows
    events: list = field(default_factory=list)
    collections: list = field(default_factory=list)
    defaults: list = field(default_factory=list)
    recoveries: list = field(default_factory=list)


def _rows(con, sql, params):
    cur = con.execute(sql, params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def life(con, app_id: str) -> Life:
    """Gather every row the application left, in date order."""
    if app_id.startswith("S"):
        sql = """SELECT app_id, app_date, product, NULL AS channel,
                        region, sector AS purpose,
                        amount_requested_cents, term_requested_months,
                        turnover_cents, sme1_score AS score, cutoff,
                        decision, decline_reason, NULL AS override,
                        offered_rate_pct, outcome, account_id
                 FROM sme_applications WHERE app_id = ?"""
    else:
        sql = """SELECT app_id, app_date, product, channel, region,
                        purpose, amount_requested_cents,
                        term_requested_months, stated_income_cents,
                        income_verified, bureau_score,
                        mark1_score AS score, cutoff, decision,
                        decline_reason, override, offered_rate_pct,
                        offered_amount_cents, offered_term_months,
                        outcome, account_id
                 FROM applications WHERE app_id = ?"""
    found = _rows(con, sql, [app_id])
    if not found:
        raise KeyError(f"no application {app_id}")
    out = Life(app=found[0])
    # A booked application has one account, or a chain of them when an
    # account continued under a new number; all carry its app_id.
    out.accounts = _rows(con, """
        SELECT account_id, product, open_date, amount_cents,
               term_months, rate_pct, rate_type, payment_cents,
               collateral_value_cents, close_date, close_reason,
               predecessor_id
        FROM accounts WHERE app_id = ?
        ORDER BY open_date, account_id""", [app_id])
    ids = [a["account_id"] for a in out.accounts]
    if not ids:
        return out
    for a in ids:
        out.months[a] = _rows(con, """
            SELECT month, balance_cents, limit_cents, scheduled_cents,
                   paid_cents, arrears_cents, missed, days_past_due,
                   status, payment_holiday
            FROM performance WHERE account_id = ?
            ORDER BY month""", [a])
    marks = ", ".join("?" for _ in ids)
    out.events = _rows(con, f"""
        SELECT account_id, event_date, event, detail
        FROM account_events WHERE account_id IN ({marks})
        ORDER BY event_date, account_id, event""", ids)
    out.collections = _rows(con, f"""
        SELECT account_id, month, action, test_arm
        FROM collections WHERE account_id IN ({marks})
        ORDER BY month, account_id, action""", ids)
    out.defaults = _rows(con, f"""
        SELECT account_id, default_month, definition, trigger,
               ead_cents, cure_month
        FROM defaults WHERE account_id IN ({marks})
        ORDER BY default_month, account_id""", ids)
    out.recoveries = _rows(con, f"""
        SELECT account_id, month, kind, amount_cents
        FROM recoveries WHERE account_id IN ({marks})
        ORDER BY month, account_id, kind""", ids)
    return out


# ------------------------------------------------------------ printing

def dollars(cents) -> str:
    """Cents to a dollar string, to the cent."""
    if cents is None:
        return "-"
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def _ym(d) -> str:
    return f"{d.year}-{d.month:02d}"


def _span(first, last) -> str:
    if first == last:
        return _ym(first)
    if first.year == last.year:
        return f"{_ym(first)}..{last.month:02d}"
    return f"{_ym(first)}..{_ym(last)}"


def month_label(row, first: bool) -> str:
    """What a month-end row says about the account, in words."""
    if first and row["scheduled_cents"] == 0 and row["paid_cents"] == 0:
        return "opened, nothing due"
    if row["payment_holiday"]:
        return "payment holiday"
    status = row["status"]
    if status == "up_to_date":
        return "up to date"
    if status in ("arrears", "default"):
        return f"{status}, {row['days_past_due']} days"
    return status.replace("_", " ")


def month_spans(rows) -> list[tuple]:
    """Runs of consecutive months that say the same thing.

    Returns (first month, last month, months, label, paid cents).
    """
    labelled = [(r, month_label(r, i == 0)) for i, r in enumerate(rows)]
    spans = []
    for label, run in groupby(labelled, key=lambda x: x[1]):
        run = [r for r, _ in run]
        paid = sum(r["paid_cents"] for r in run)
        spans.append((run[0]["month"], run[-1]["month"], len(run),
                      label, paid))
    return spans


def _runs(rows, date_key, label_key):
    """Consecutive rows with the same label: (first, last, n, label)."""
    out = []
    for label, run in groupby(rows, key=lambda r: r[label_key]):
        run = list(run)
        out.append((run[0][date_key], run[-1][date_key], len(run),
                    label))
    return out


def _clip(lines, most, what):
    if len(lines) <= most:
        return lines
    return lines[:most] + [f"  ... and {len(lines) - most} more {what}"]


def _words(code) -> str:
    return code.replace("_", " ")


def _application(a) -> list[str]:
    where = [a["product"], a["channel"], str(a["app_date"]),
             a["region"]]
    out = [f"{a['app_id']}  " + ", ".join(w for w in where if w)]
    asked = "a card"
    if a["amount_requested_cents"]:
        asked = dollars(a["amount_requested_cents"])[:-3]
    if a["term_requested_months"]:
        asked += f" over {a['term_requested_months']} months"
    out.append(f"  asked      {asked} ({_words(a['purpose'])})")
    if "stated_income_cents" in a:
        income = dollars(a["stated_income_cents"])[:-3]
        checked = "verified" if a["income_verified"] else "not verified"
        bureau = a["bureau_score"] or "no file"
        out.append(f"  told us    income {income} ({checked});"
                   f" bureau {bureau}")
    out.append(f"  decided    {a['decision']}: score {a['score']},"
               f" cut-off {a['cutoff']}")
    why = a["decline_reason"] or a["override"]
    if why:
        out.append(f"             ({_words(why)})")
    if a["decision"] == "approve":
        offer = f"{a['offered_rate_pct']}%"
        if a.get("offered_amount_cents"):
            amount = dollars(a["offered_amount_cents"])[:-3]
            offer = f"{amount} at {offer}"
        out.append(f"  offered    {offer}; {_words(a['outcome'])}")
    return out


def _account(acc, rows, most) -> list[str]:
    out = [f"account     {acc['account_id']} opened {acc['open_date']},"
           f" {_words(acc['rate_type'])} {acc['rate_pct']}%"]
    if acc["payment_cents"]:
        out.append(f"  pays       {dollars(acc['payment_cents'])}"
                   f" a month over {int(acc['term_months'])} months")
    if acc["collateral_value_cents"]:
        value = dollars(acc["collateral_value_cents"])
        out.append(f"  secured on {value} of collateral")
    ended = "still open"
    if acc["close_date"]:
        last = dollars(rows[-1]["balance_cents"])
        ended = (f"{acc['close_date']} {_words(acc['close_reason'])},"
                 f" balance {last}")
    out.append(f"  closed     {ended}")
    out.append(f"  months     {len(rows)} month ends")
    spans = [f"  {_span(f, last):<17}{n:>3}  {label:<21}"
             f"paid {dollars(paid):>11}"
             for f, last, n, label, paid in month_spans(rows)]
    return out + _clip(spans, most, "runs")


def _events(lf) -> list[str]:
    return [f"  {e['event_date']}  {e['account_id']}  "
            f"{_words(e['event'])}" for e in lf.events]


def _collections(lf) -> list[str]:
    runs = _runs(lf.collections, "month", "action")
    return [f"  {_span(f, last):<17}{n:>3}  {_words(act)}"
            for f, last, n, act in runs]


def _defaults(lf) -> list[str]:
    out = []
    for d in lf.defaults:
        line = (f"  {d['default_month']}  {d['definition']:<8}"
                f"{_words(d['trigger']):<14}"
                f"owed {dollars(d['ead_cents'])}")
        if d["cure_month"]:
            line += f", cured {_ym(d['cure_month'])}"
        out.append(line)
    return out


# The order recoveries usually arrive in, for printing.
KINDS = ("guarantee", "collateral_sale", "collections_payment",
         "debt_sale", "cost")


def _recoveries(lf) -> list[str]:
    out = []
    for k in KINDS:
        mine = [r for r in lf.recoveries if r["kind"] == k]
        if not mine:
            continue
        total = sum(r["amount_cents"] for r in mine)
        when = _span(mine[0]["month"], mine[-1]["month"])
        out.append(f"  {when:<17}{len(mine):>3}  {_words(k):<21}"
                   f"{dollars(total):>16}")
    if out:
        net = sum(r["amount_cents"] for r in lf.recoveries)
        out.append(f"  {'net of costs':<43}{dollars(net):>16}")
    return out


def format_life(lf: Life, most: int = 10) -> list[str]:
    """The life as lines of at most 68 characters."""
    out = _application(lf.app)
    if not lf.accounts:
        return out + ["account     none"]
    for acc in lf.accounts:
        out += _account(acc, lf.months[acc["account_id"]], most)
    for title, items in (("events", _events(lf)),
                         ("collections", _collections(lf)),
                         ("defaults", _defaults(lf)),
                         ("recoveries", _recoveries(lf))):
        out.append(title if items else f"{title:<12}none")
        out += _clip(items, most, title)
    return out


def print_life(con, app_id: str, most: int = 10) -> None:
    """Print one application's life, from the form to the last row."""
    for line in format_life(life(con, app_id), most):
        print(line)
