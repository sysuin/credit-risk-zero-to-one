#!/usr/bin/env python3
"""Prove the loan book has the properties the chapters rely on.

    python code/fernhill/verify.py

Each check measures one thing a chapter will find, and fails if it is not there. A lesson
the data does not contain is a chapter that cannot be written; this is where that shows
up first, before anyone has written a word of it.
"""
from __future__ import annotations

import sys

import duckdb

from ballast.config import LOANBOOK, TRUTH

FAILS: list[str] = []


def check(label: str, value, ok: bool, detail: str = "") -> None:
    shown = f"{value:.4f}" if isinstance(value, float) else str(value)
    print(f"  {'PASS' if ok else 'FAIL'}  {label:<58} {shown:>10}  {detail}")
    if not ok:
        FAILS.append(label)


def main() -> int:
    c = duckdb.connect(str(LOANBOOK), read_only=True, config={"threads": 1})
    c.execute(f"ATTACH '{TRUTH}' AS truth (READ_ONLY)")
    one = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731

    print("\nSize")
    n_apps = one("SELECT count(*) FROM applications")
    n_acc = one("SELECT count(*) FROM accounts")
    n_perf = one("SELECT count(*) FROM performance")
    check("consumer applications", n_apps, 150_000 < n_apps < 220_000)
    check("accounts", n_acc, 60_000 < n_acc < 120_000)
    check("performance rows", n_perf, 1_500_000 < n_perf < 4_000_000)

    print("\nDefault rates (first 90 days past due, by calendar year)")
    rates = dict(c.execute("""
        WITH f AS (SELECT account_id, product, min(month) m FROM performance WHERE missed >= 3 GROUP BY ALL),
        s AS (SELECT product, year(month) + 1 y, count(DISTINCT account_id) n FROM performance
              WHERE month(month) = 12 AND status IN ('up_to_date', 'arrears') GROUP BY ALL)
        SELECT s.product, count(f.account_id) / sum(DISTINCT s.n)
        FROM s LEFT JOIN f ON f.product = s.product AND year(f.m) = s.y
        WHERE s.y BETWEEN 2017 AND 2025 GROUP BY s.product""").fetchall())
    for prod, lo, hi in (("personal", 0.025, 0.06), ("card", 0.02, 0.05), ("auto", 0.015, 0.04),
                         ("mortgage", 0.002, 0.01), ("sme_term", 0.015, 0.05)):
        check(f"{prod} default rate, 2017-2025 average", float(rates.get(prod, 0)), lo < rates.get(prod, 0) < hi)
    shock = one("""WITH f AS (SELECT account_id, min(month) m FROM performance WHERE missed >= 3 AND product = 'personal' GROUP BY 1)
                   SELECT count(*) FILTER (WHERE year(m) = 2020) / count(*) FILTER (WHERE year(m) = 2019) FROM f""")
    check("personal defaults 2020 / 2019", float(shock), shock > 1.4, "the shock shows")

    print("\nThe bureau's new scale (Chapters 5, 11, 24)")
    v2 = one("SELECT avg(bureau_score) FROM applications WHERE bureau_version = 'v2'")
    v3 = one("SELECT avg(bureau_score) FROM applications WHERE bureau_version = 'v3'")
    check("mean bureau score, v3 minus v2", float(v3 - v2), v3 - v2 > 25)
    creep = one("""SELECT avg((decision = 'approve')::int) FILTER (WHERE app_date >= DATE '2019-07-01')
                        - avg((decision = 'approve')::int) FILTER (WHERE app_date < DATE '2019-07-01')
                   FROM applications WHERE product = 'personal' AND app_date BETWEEN DATE '2019-01-01' AND DATE '2020-03-31'""")
    check("personal approval rate up after v3 (same cut-off)", float(creep), creep > 0.02)

    print("\nPrice test and adverse selection (Chapter 12)")
    tu = dict(c.execute("""SELECT price_test_arm, avg((outcome = 'booked')::int) FROM applications
                           WHERE price_test_arm IS NOT NULL GROUP BY 1""").fetchall())
    check("take-up, minus_150 arm minus plus_150 arm", float(tu["minus_150"] - tu["plus_150"]), tu["minus_150"] - tu["plus_150"] > 0.05)
    adv = one("""SELECT avg(d) FROM (
                   SELECT round(offered_rate_pct) r, avg(z) FILTER (WHERE outcome = 'booked')
                          - avg(z) FILTER (WHERE outcome = 'not_taken_up') d, count(*) n
                   FROM applications JOIN truth.applicants USING (app_id)
                   WHERE product = 'personal' AND decision = 'approve' GROUP BY 1) WHERE n >= 200""")
    check("latent quality, booked minus walked away, same price", float(adv), adv < -0.05, "worse ones stay")

    print("\nRejects (Chapter 9)")
    rej = one("""SELECT avg(bad_12m_if_booked::int) FROM truth.origination JOIN applications USING (app_id)
                 WHERE outcome = 'declined' AND product = 'personal'""")
    acc12 = one("""SELECT avg(CASE WHEN pd12_at_open > 0 THEN pd12_at_open END) FROM truth.origination
                   JOIN applications USING (app_id) WHERE outcome = 'booked' AND product = 'personal'""")
    check("declined personal applicants' true 12-month bad rate", float(rej), rej > 2 * acc12, f"booked pd12 {acc12:.4f}")
    retro = one("SELECT count(*) FROM bureau_retro WHERE opened_elsewhere")
    check("rejects and walk-aways seen by the bureau elsewhere", retro, retro > 10_000)

    print("\nFraud (Chapter 13)")
    fpd = one("""WITH first_due AS (SELECT account_id, min(month) m FROM performance WHERE scheduled_cents > 0 GROUP BY 1)
                 SELECT avg((p.missed >= 1)::int) FROM performance p JOIN first_due f ON p.account_id = f.account_id AND p.month = f.m
                 JOIN accounts a ON a.account_id = p.account_id JOIN truth.applicants t ON t.app_id = a.app_id WHERE t.fraud""")
    check("fraud accounts missing their first payment", float(fpd), fpd > 0.9)

    print("\nPayment holidays and what they hid (Chapters 6, 24, 25)")
    hol = one("SELECT count(DISTINCT account_id) FROM account_events WHERE event = 'payment_holiday_start'")
    check("accounts given a payment holiday", hol, hol > 2000)
    after = c.execute("""
        WITH h AS (SELECT account_id, max(event_date) ended FROM account_events WHERE event = 'payment_holiday_end' GROUP BY 1)
        SELECT avg(CASE WHEN h.account_id IS NOT NULL THEN bad END), avg(CASE WHEN h.account_id IS NULL THEN bad END)
        FROM (SELECT p.account_id, max((p.missed >= 1)::int) bad FROM performance p
              WHERE p.month BETWEEN DATE '2020-10-31' AND DATE '2021-06-30' GROUP BY 1) b
        LEFT JOIN h USING (account_id)""").fetchone()
    check("missed a payment Oct 2020-Jun 2021: holiday / none", float(after[0] / after[1]), after[0] > 1.6 * after[1])

    print("\nDefinition of default (Chapter 6)")
    old = one("SELECT count(*) FROM defaults WHERE definition = 'dpd90'")
    new = one("SELECT count(*) FROM defaults WHERE definition = 'dod2021'")
    immaterial = one("""SELECT count(DISTINCT account_id) FROM performance WHERE month >= DATE '2021-01-31' AND missed >= 3
                        AND (arrears_cents <= 10000 OR arrears_cents <= 0.01 * balance_cents)""")
    check("defaults recorded under each definition", f"{old}/{new}", old > 1000 and new > 1000)
    check("accounts 90+ DPD but not materially in arrears", immaterial, immaterial > 50)
    utp = one("SELECT count(*) FROM defaults WHERE trigger <> 'days_past_due'")
    check("defaults triggered by bankruptcy or charge-off", utp, utp > 100)

    print("\nExposure at default (Chapter 19)")
    ccf = c.execute("""
        WITH d AS (SELECT account_id, min(month) m FROM performance WHERE product = 'card' AND missed >= 3 GROUP BY 1)
        SELECT avg(p0.balance_cents / p0.limit_cents), avg(p1.balance_cents / p1.limit_cents)
        FROM d JOIN performance p0 ON p0.account_id = d.account_id AND p0.month = last_day(d.m - INTERVAL 12 MONTH)
               JOIN performance p1 ON p1.account_id = d.account_id AND p1.month = d.m
        WHERE p0.limit_cents > 0""").fetchone()
    check("defaulted cards: utilisation 12 months before / at default", f"{ccf[0]:.2f}/{ccf[1]:.2f}", ccf[1] > ccf[0] + 0.15)

    print("\nLoss given default (Chapter 19)")
    lgd = dict(c.execute("""
        WITH d AS (SELECT account_id, min(default_month) dm, any_value(ead_cents) ead FROM defaults GROUP BY 1),
        r AS (SELECT account_id, sum(amount_cents) rec FROM recoveries GROUP BY 1)
        SELECT a.product, 1 - sum(coalesce(r.rec, 0)) / sum(d.ead) FROM d JOIN accounts a USING (account_id)
        LEFT JOIN r USING (account_id) WHERE d.dm <= DATE '2021-12-31' AND d.ead > 0
        AND d.account_id IN (SELECT account_id FROM accounts WHERE close_reason IN
              ('charged_off', 'vehicle_repossessed', 'property_sold', 'collateral_sold'))
        GROUP BY 1""").fetchall())
    for prod, lo, hi in (("personal", 0.6, 0.95), ("card", 0.7, 0.98), ("auto", 0.2, 0.7), ("sme_emergency", 0.0, 0.4)):
        v = lgd.get(prod)
        check(f"{prod} realised LGD, closed workouts, defaults to 2021", float(v) if v is not None else -1.0,
              v is not None and lo < v < hi)
    sales = one("SELECT count(*) FROM recoveries WHERE kind = 'debt_sale'")
    check("charged-off accounts sold to debt buyers", sales, sales > 100)

    print("\nRates and mortgages (Chapters 3, 26)")
    shock = c.execute("""
        WITH f AS (SELECT account_id, min(month) m FROM performance WHERE missed >= 1
                   AND month BETWEEN DATE '2023-01-01' AND DATE '2024-12-31' GROUP BY 1)
        SELECT a.rate_type, count(f.account_id) / count(*) FROM accounts a LEFT JOIN f ON f.account_id = a.account_id
        WHERE a.product = 'mortgage' AND a.open_date < DATE '2022-01-01' GROUP BY 1 ORDER BY 1""").fetchall()
    sd = dict(shock)
    check("mortgages in arrears 2023-24: variable / fixed", float(sd["variable"] / max(sd["fixed"], 1e-9)), sd["variable"] > sd["fixed"])

    print("\nCollections test (Chapter 25)")
    ct = dict(c.execute("""
        WITH t AS (SELECT account_id, min(month) m, any_value(test_arm) arm FROM collections WHERE test_arm IS NOT NULL GROUP BY 1)
        SELECT arm, avg(CASE WHEN p.missed = 0 THEN 1 ELSE 0 END) FROM t
        JOIN performance p ON p.account_id = t.account_id AND p.month = last_day(t.m + INTERVAL 1 MONTH) GROUP BY 1""").fetchall())
    check("cured next month: call_first minus sms_first", float(ct["call_first"] - ct["sms_first"]), ct["call_first"] > ct["sms_first"])

    print("\nStated income (Chapters 5, 13)")
    infl = dict(c.execute("""SELECT channel, avg(stated_income_cents / true_income_cents) FROM applications
                             JOIN truth.applicants USING (app_id) WHERE NOT fraud GROUP BY 1""").fetchall())
    check("stated over true income: broker / branch", float(infl["broker"] / infl["branch"]), infl["broker"] > infl["branch"] * 1.08)

    print("\nCards moved to a new processor (Chapter 6)")
    mig = one("SELECT count(*) FROM accounts WHERE close_reason = 'migrated'")
    check("card accounts migrated in March 2022", mig, mig > 3000)

    print("\nFair lending (Chapter 13)")
    g = dict(c.execute("""SELECT gender, avg((decision = 'approve')::int) FROM applications JOIN applicant_monitoring USING (app_id)
                          WHERE product = 'personal' GROUP BY 1""").fetchall())
    check("approval rate, women minus men", float(g["F"] - g["M"]), g["F"] < g["M"])

    print("\nSmall business and the emergency loans (Chapters 16, 19)")
    em = one("""SELECT count(DISTINCT account_id) FILTER (WHERE missed >= 3) / count(DISTINCT account_id)
                FROM performance WHERE product = 'sme_emergency'""")
    check("emergency loans ever 90 days past due", float(em), em > 0.12)
    gt = one("SELECT count(*) FROM recoveries WHERE kind = 'guarantee'")
    check("government guarantee claims paid", gt, gt > 100)

    print("\nThe commercial book (Chapters 14-18)")
    nd = one("SELECT count(*) FROM corporate_defaults")
    check("corporate defaults, 2016-2025", nd, 8 <= nd <= 60)
    ny = one("SELECT count(DISTINCT year(default_month)) FROM corporate_defaults")
    check("years with at least one corporate default", ny, ny >= 5)
    mer = one("SELECT count(*) FROM financials f JOIN companies c USING (company_id) WHERE c.name = 'Meridian Supply Co.'")
    check("Meridian's annual accounts", mer, mer == 4)
    listed = one("SELECT count(DISTINCT company_id) FROM market_data")
    check("listed companies with share prices", listed, listed >= 40)
    sticky = one("""WITH r AS (SELECT company_id, rating_date, internal_grade, lag(internal_grade) OVER (PARTITION BY company_id ORDER BY rating_date) prev
                    FROM ratings WHERE internal_grade IS NOT NULL)
                    SELECT avg((internal_grade = prev)::int) FROM r WHERE prev IS NOT NULL""")
    check("internal grades unchanged at annual review", float(sticky), sticky > 0.4)

    print("\nFixes found while writing Part I")
    cli = one("""SELECT count(DISTINCT p.account_id) FROM performance p JOIN accounts a USING (account_id)
                 WHERE p.product = 'card' AND p.limit_cents > a.amount_cents""")
    check("cards given a credit line increase", cli, cli > 1000)
    surplus = one("""WITH r AS (SELECT account_id, sum(amount_cents) rec FROM recoveries
                               WHERE kind = 'collateral_sale' GROUP BY 1),
                     e AS (SELECT account_id, max(balance_cents) owed FROM performance GROUP BY 1)
                     SELECT count(*) FROM r JOIN e USING (account_id) WHERE rec > owed * 1.2 + 1000000""")
    check("collateral sales returning far more than was ever owed", surplus, surplus == 0)
    sold = one("SELECT count(*) FROM accounts WHERE close_reason = 'collateral_sold'")
    check("secured business loans worked out through their security", sold, sold > 20)
    ratio = one("""SELECT max(lim) / min(lim) FROM (SELECT year(month) y, sum(limit_cents) lim FROM facility_months
                   WHERE month(month) = 12 AND status = 'performing' GROUP BY 1)""")
    check("commercial limits, largest year / smallest", float(ratio), ratio < 1.6, "the book renews")
    em = one("""SELECT max(abs(a.payment_cents - p.scheduled_cents)) FROM accounts a JOIN performance p USING (account_id)
                WHERE a.product = 'sme_emergency' AND p.scheduled_cents > 0""")
    check("emergency loans: first instalment equals booked payment (cents)", em, em <= 1)

    art = one("""WITH f AS (SELECT company_id, fiscal_year, equity_cents, net_income_cents, dividends_cents,
                         lag(equity_cents) OVER (PARTITION BY company_id ORDER BY fiscal_year) prev,
                         lag(fiscal_year) OVER (PARTITION BY company_id ORDER BY fiscal_year) prev_year FROM financials)
                  SELECT max(abs(equity_cents - prev - net_income_cents + dividends_cents)) FROM f
                  WHERE prev_year = fiscal_year - 1""")
    check("accounts articulate: equity moves by profit less dividends", art, art <= 300)
    payout = one("""SELECT dividends_cents / net_income_cents FROM financials JOIN companies USING (company_id)
                    WHERE name = 'Meridian Supply Co.' AND fiscal_year = 2025""")
    check("Meridian's 2025 payout ratio", float(payout), payout > 0.4, "the owners take cash out")

    orphans = one("SELECT count(*) FROM recoveries WHERE account_id IS NULL")
    check("recoveries without an account", orphans, orphans == 0)
    dup = one("SELECT count(*) FROM (SELECT facility_id, month FROM facility_months GROUP BY ALL HAVING count(*) > 1)")
    check("facility-months recorded twice", dup, dup == 0)

    print(f"\n  {'All checks passed.' if not FAILS else f'{len(FAILS)} failed: ' + '; '.join(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
