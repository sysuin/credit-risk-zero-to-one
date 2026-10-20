"""Meridian's case, assembled once for the term sheet and the memo.

Every number comes from the spread and from ballast.commercial.
structure, by the same calls the chapter's earlier listings make;
the words are the analyst's.
"""
from __future__ import annotations

from ballast.commercial import memo as mm
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st

MARGIN_BPS = 200
MAX_INELIGIBLE = 0.25          # condition: aged listing at or below


def analysis(con) -> dict:
    """The numbers the term sheet and the memo quote."""
    m = sp.company_id(con, "Meridian Supply Co.")
    s = sp.spread(sp.accounts(con, m))
    r = sp.ratios(s)
    c = s[2025]
    need = st.revolver_need(s, 2025,
                            growth=float(r.loc["revenue_growth", 2025]))
    limit = int(need.limit)
    pf = st.pro_forma(s, 2025, add=limit, keep=int(c.long_term_debt),
                      rate_new=c.interest / c.total_debt)
    cap, floor = st.covenant_levels(pf.leverage, pf.cover)
    bb = st.borrowing_base(c.receivables, c.inventory)
    allowed = st.permitted_distribution(int(c.net_income),
                                        float(r.loc["leverage", 2025]))
    req = con.execute("""SELECT amount_cents, request_date
        FROM credit_requests WHERE request_id = 'R2025-117'
        """).fetchone()
    at_default = con.execute("""
        SELECT avg(x.drawn_cents / x.limit_cents)
        FROM facility_months x JOIN facilities f USING (facility_id)
        WHERE f.kind = 'revolver' AND x.status = 'defaulted'
        """).fetchone()[0]
    income = [st.facility_income(limit, round(limit * u),
                                 MARGIN_BPS).total for u in (0.3, 0.9)]
    return dict(s=s, r=r, need=need, limit=limit, pf=pf, cap=cap,
                floor=floor, bb=bb, allowed=allowed, request=req,
                at_default=at_default, income=income,
                loss_cost=book_loss_cost(con, limit)["cost"])


def book_loss_cost(con, limit: int) -> dict:
    """A year's expected loss on `limit` from Fernhill's averages:
    the commercial default rate (clients with a performing facility
    at a year end, defaulting the next year), the loss on secured
    revolvers after recoveries, and how far they were drawn at
    default. Returns each part and the cost."""
    pd_book = con.execute("""
        WITH alive AS (
            SELECT DISTINCT f.company_id, year(m.month) + 1 AS y
            FROM facility_months m JOIN facilities f
              USING (facility_id)
            WHERE month(m.month) = 12 AND m.status = 'performing')
        SELECT count(d.company_id) / count(*) FROM alive a
        LEFT JOIN corporate_defaults d
          ON d.company_id = a.company_id
         AND year(d.default_month) = a.y
        WHERE a.y <= 2025""").fetchone()[0]
    drawn, back = con.execute("""
        WITH e AS (SELECT facility_id, drawn_cents, limit_cents
                   FROM facility_months WHERE status = 'defaulted'),
        r AS (SELECT facility_id, sum(amount_cents) AS net
              FROM corporate_recoveries GROUP BY 1)
        SELECT sum(e.drawn_cents) / sum(e.limit_cents),
               sum(r.net) / sum(e.drawn_cents)
                 FILTER (WHERE r.net IS NOT NULL)
        FROM e JOIN facilities f USING (facility_id)
        LEFT JOIN r USING (facility_id)
        WHERE f.kind = 'revolver' AND f.secured""").fetchone()
    return {"pd": pd_book, "loss": 1 - back, "drawn": drawn,
            "cost": pd_book * (1 - back) * drawn * limit}


def terms(a: dict) -> st.TermSheet:
    return st.TermSheet(
        borrower="Meridian Supply Co.",
        limit_cents=a["limit"], tenor_months=36,
        purpose="Working capital: to replace Meridian's short-term "
                "borrowing and to carry its receivables and stock "
                "as sales grow. Not for distributions or "
                "acquisitions.",
        margin_bps=MARGIN_BPS, reference="Reference rate",
        max_leverage=a["cap"], min_cover=a["floor"],
        security="First-ranking security over all receivables, "
                 "inventory and the collection account customers "
                 "pay into; general security over other assets.",
        guarantees="Every group company that holds receivables or "
                   "inventory. No personal guarantee.",
        ranking="Senior. Intercreditor agreement with the existing "
                "term lender: Fernhill first on receivables and "
                "stock, the term lender first on fixed assets.",
        reporting=["borrowing base certificate and aged receivables "
                   "monthly, within 20 days",
                   "management accounts and covenant certificate "
                   "quarterly",
                   "audited accounts within 120 days of year end",
                   "a field examination of receivables and stock "
                   "once a year"],
        conditions=["audited 2025 accounts, not materially worse "
                    "than the management accounts",
                    "aged receivables at 31 December 2025 with "
                    f"ineligibles at or below {MAX_INELIGIBLE:.0%}",
                    "short-term borrowing repaid and its security "
                    "released", "intercreditor agreement signed"])


def memo(a: dict) -> mm.Memo:
    s, r, pf, t = a["s"], a["r"], a["pf"], terms(a)
    amount, when = a["request"]
    limit_m = a["limit"] / 1e8
    years, rows = mm.key_figures(s, r, extra={"PF": {
        "total_debt": pf.debt, "leverage": pf.leverage,
        "interest_cover": pf.cover}})
    paid = s.loc["dividends", 2025]
    lev, cov = r.loc["leverage", 2025], r.loc["interest_cover", 2025]
    return mm.Memo(
        borrower="Meridian Supply Co. (prospect, wholesale)",
        request=f"R2025-117, {when:%d %B %Y}: ${amount / 1e8:.0f}m "
                "revolver, 36 months",
        prepared="5 January 2026, for the credit committee",
        decision="approve a smaller, structured facility",
        recommendation=(
            f"Approve a ${limit_m:.0f}m committed revolving facility "
            f"for 36 months in place of the ${amount / 1e8:.0f}m "
            "requested. It replaces Meridian's "
            f"${a['need'].refinance / 1e8:.2f}m of short-term "
            "borrowing and carries two years of working-capital "
            "growth at 2025's pace. Drawings are limited to a "
            "borrowing base on receivables and stock, secured first "
            f"on both. Leverage is capped at {a['cap']:.2f}x and "
            f"interest cover held at {a['floor']:.2f}x or more, "
            "about 30% EBITDA headroom fully drawn; distributions "
            f"are limited to {st.PAYOUT_CAP:.0%} of the previous "
            "year's profit. Approval is conditional on the audited "
            "2025 accounts and the aged receivables listing."),
        terms=t, figures=rows, figure_years=years,
        case_for=[
            f"Leverage {lev:.2f}x and interest cover {cov:.2f}x in "
            "2025, at the safe end of Fernhill's wholesale clients; "
            f"fully drawn, {pf.leverage:.2f}x and {pf.cover:.2f}x.",
            "Profitable in every year; revenue up "
            f"{s.loc['revenue', 2025] / s.loc['revenue', 2022]:.2f} "
            "times since 2022 with a steady gross margin.",
            "The request matches the need: working capital that has "
            "grown with sales, funded by a facility that revolves.",
        ],
        risks=[
            ("Receivable days rose from "
             f"{r.loc['receivable_days', 2022]:.0f} to "
             f"{r.loc['receivable_days', 2025]:.0f}; the cause is "
             "not yet known.",
             "Overdue and concentrated invoices are ineligible and "
             "certified monthly; the aged listing is a condition."),
            ("Free cash flow was negative in three of four years.",
             f"The limit is sized to need, ${limit_m:.0f}m, not to "
             "the request; any increase returns to committee."),
            (f"{r.loc['payout', 2025]:.0%} of 2025's profit was paid "
             "out while debt rose.",
             "Distributions capped; the 2026 allowance is "
             f"${a['allowed'] / 1e8:.2f}m against "
             f"${paid / 1e8:.2f}m paid in 2025."),
            ("The 2025 figures are unaudited.",
             "Audited accounts are a condition of first drawing."),
            ("Revolvers are drawn hardest as borrowers weaken: "
             f"Fernhill's were {a['at_default']:.0%} drawn at "
             "default.",
             "The base falls as receivables age, before an annual "
             "covenant test could see it."),
        ],
        conditions=t.conditions,
        questions=[
            "Why receivable days rose, and which customers owe the "
            "oldest balances.",
            "Dividends planned for 2026 and 2027.",
            "Whether suppliers have shortened Meridian's terms.",
            "Who the term lender is, and its schedule and security.",
        ],
        rating="Internal grade to be assigned under the commercial "
               "rating model before committee. Until then the loss "
               "cost uses Fernhill's book averages: about "
               f"${a['loss_cost'] / 1e5:,.0f}k a year against "
               f"${a['income'][0] / 1e5:,.0f}k to "
               f"${a['income'][1] / 1e5:,.0f}k of margin and fees.",
    )
