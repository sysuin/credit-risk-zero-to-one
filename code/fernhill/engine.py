"""The month-end engine: how every retail and small-business account behaves, month by
month, from the day it opens to the end of 2025.

Each month an account that is up to date may miss a payment. One that is behind may catch
up (a cure), stay where it is, or fall further behind (a roll). Three missed payments is
90 days past due. After that it may still cure, or it runs on to charge-off, repossession
or the sale of the property behind it. The chance of the first miss rises with the
borrower's latent risk, the burden of the payment on their true income, the account's age
on book, and the economy; it is the "true hazard" the truth database keeps.

The same transition probabilities give each account's true chance of reaching 90 days past
due in the next twelve months, which the engine works out exactly (a four-state Markov
chain stepped twelve times) and keeps as `pd12`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fernhill.applicants import sigmoid

# Product parameters. c: base log-odds of a first missed payment; bz: weight on latent
# risk; burden: weight on payment-to-income above 30%; macro: sensitivity to the economy;
# prepay: monthly chance an up-to-date account repays early; chargeoff: missed payments
# at which the debt is written off; post_cure: monthly chance a defaulted account
# catches up.
PARAMS = {
    "personal":      dict(c=-4.30, bz=0.95, burden=2.2, macro=1.00, prepay=0.013, chargeoff=6, post_cure=0.045),
    "card":          dict(c=-4.45, bz=0.95, burden=1.2, macro=1.05, prepay=0.004, chargeoff=6, post_cure=0.035),
    "auto":          dict(c=-4.75, bz=0.90, burden=2.0, macro=0.85, prepay=0.015, chargeoff=6, post_cure=0.060),
    "mortgage":      dict(c=-6.10, bz=0.85, burden=4.0, macro=0.80, prepay=0.005, chargeoff=99, post_cure=0.070),
    "sme_term":      dict(c=-4.35, bz=0.90, burden=1.5, macro=1.00, prepay=0.008, chargeoff=6, post_cure=0.040),
    "sme_overdraft": dict(c=-4.45, bz=0.90, burden=1.0, macro=1.00, prepay=0.000, chargeoff=6, post_cure=0.040),
    "sme_emergency": dict(c=-3.75, bz=0.80, burden=1.0, macro=1.10, prepay=0.004, chargeoff=6, post_cure=0.030),
}
REVOLVING = {"card", "sme_overdraft"}


def seasoning(age: np.ndarray) -> np.ndarray:
    """Log-odds adjustment for months on book: low at first, a peak at about 14 months,
    then a slow fall as the borrowers who were going to struggle have done so."""
    a = np.maximum(age, 1).astype(float)
    x = a / 14.0
    return np.maximum(0.8 * np.log(x * np.exp(1 - x)), -2.0)


@dataclass
class Accounts:
    """Everything the engine needs about each account, one array per field."""
    account_id: np.ndarray
    product: np.ndarray
    open_t: np.ndarray            # month index of the open month (0 = Jan 2016)
    amount: np.ndarray            # principal, or the credit limit for revolving accounts
    term: np.ndarray              # months; 0 for revolving
    rate: np.ndarray              # annual %, at opening
    rate_type: np.ndarray         # 'fixed', 'variable', 'fixed_then_variable'
    fixed_months: np.ndarray
    margin: np.ndarray            # over the policy rate, once variable
    z: np.ndarray
    income: np.ndarray            # true monthly income at opening
    other_payments: np.ndarray
    fraud: np.ndarray
    macro_sens: np.ndarray        # region or sector multiplier on the economy
    shock_2020: np.ndarray        # extra log-odds in the 2020 shock (sector-specific)
    holiday_free: np.ndarray      # months with no payment due at the start (emergency loans)
    shadow: np.ndarray            # a declined applicant run for twelve months, for the truth
    rng_seed: int = 0
    extra: dict = field(default_factory=dict)


def run(acc: Accounts, macro: pd.DataFrame, stress: np.ndarray, forward_stress: np.ndarray,
        forward_rate: np.ndarray, rng: np.random.Generator):
    n = len(acc.account_id)
    T = len(macro)
    cli_rng = np.random.default_rng(acc.rng_seed + 1)
    months = pd.to_datetime(macro["month"]).dt.date.to_numpy()
    policy = macro["policy_rate_pct"].to_numpy()
    stress_all = np.concatenate([stress, forward_stress])
    policy_all = np.concatenate([policy, forward_rate])

    prod = acc.product
    P = {k: np.array([PARAMS[p][k] for p in prod]) for k in ("c", "bz", "burden", "macro", "prepay", "chargeoff", "post_cure")}
    # Secured business loans are worked out through their security, not written off early.
    P["chargeoff"] = np.where((prod == "sme_term") & acc.extra["secured"], 12, P["chargeoff"])
    shock_w = np.select([prod == "mortgage", prod == "sme_term"], [2.6, 1.2], 0.0)
    payment0 = np.zeros(n)
    revolving = np.isin(prod, list(REVOLVING))

    # State
    status = np.zeros(n, dtype=np.int8)       # 0 not yet open, 1 open, 2 closed
    missed = np.zeros(n, dtype=np.int16)
    balance = np.zeros(n)
    limit = np.where(revolving, acc.amount, 0.0)
    rate = acc.rate.astype(float).copy()
    term_left = acc.term.astype(float).copy()
    payment = np.zeros(n)
    util = np.zeros(n)
    util_base = np.clip(0.35 - 0.16 * acc.z + rng.normal(0, 0.12, n), 0.02, 0.95)
    transactor = revolving & (prod == "card") & (rng.random(n) < sigmoid(-0.6 + 0.9 * acc.z))
    util_base = np.where(transactor, util_base * 0.4, util_base)
    holiday_left = np.zeros(n, dtype=np.int16)
    holiday_used = np.zeros(n, dtype=bool)
    bump_left = np.zeros(n, dtype=np.int16)
    bankrupt = np.zeros(n, dtype=bool)
    ever_default = np.zeros(n, dtype=bool)
    in_default = np.zeros(n, dtype=bool)
    default_t = np.full(n, -1)
    default_age = np.full(n, -1)
    income = acc.income.astype(float).copy()
    noise = rng.normal(0, 0.25, n)           # what the borrower knows and nobody else does
    # Trouble comes and goes: a job lost, an illness, a divorce. A slowly decaying shock
    # that raises the chance of missing a payment and, on a card or an overdraft, the
    # balance, months before anything is missed.
    trouble = np.zeros(n)
    RHO, TROUBLE_SD = 0.88, 0.75

    trouble_now = np.zeros(n)
    rows = []
    events = []        # (account index, t, event)
    defaults = []      # (account index, t, ead, missed at event)
    closes = []        # (account index, t, reason, balance)
    pd12_rows = []     # (account index, t, pd12)
    shadow_bad = np.zeros(n, dtype=bool)

    def logit_first_miss(idx, t, age, extra_burden=0.0):
        burden = (acc.other_payments[idx] + payment[idx]) / np.maximum(income[idx], 1) - 0.30
        lg = (P["c"][idx] - P["bz"][idx] * acc.z[idx] + P["burden"][idx] * np.clip(burden + extra_burden, -0.3, 0.7)
              + seasoning(age) + P["macro"][idx] * acc.macro_sens[idx] * stress_all[t] + noise[idx]
              + trouble_now[idx]
              # A payment that has risen since the loan was taken out bites harder than
              # one the borrower planned for: the payment-shock effect.
              + shock_w[idx] * np.log(np.maximum(payment[idx], 1) / np.maximum(payment0[idx], 1)).clip(0, None))
        if 51 <= t <= 56:   # April to September 2020
            lg = lg + acc.shock_2020[idx]
        lg = lg + 1.2 * (bump_left[idx] / 6.0)
        return lg

    def p_cure(idx, t):
        # The 2024 collections test: accounts falling behind that year were phoned first
        # or texted first, at random. Phoning first works a little better.
        test = (acc.extra["collections_arm"][idx] == "call_first") & (96 <= t <= 107)
        return sigmoid(-0.55 + 0.75 * acc.z[idx] - 0.45 * stress_all[t] + 0.25 * test)

    def p_roll(idx, t, m):
        return sigmoid(-0.35 - 0.80 * acc.z[idx] + 0.55 * stress_all[t] + 0.45 * (m >= 2))

    def pd12_for(idx, t, age):
        """The probability of reaching three missed payments within twelve months, from
        each account's state at this month end, under the realised economy (and the base
        scenario after December 2025). Exact for the engine's own transition
        probabilities, with closures by maturity and early repayment as a competing exit,
        so it can be compared with what actually happened."""
        k = len(idx)
        dist = np.zeros((k, 5))           # up to date, 1 missed, 2 missed, default, closed
        m0 = np.clip(missed[idx], 0, 3)
        dist[np.arange(k), m0] = 1.0
        saved_bump = bump_left[idx].copy()
        saved_trouble = trouble_now[idx].copy()
        inst = ~revolving[idx]
        for step in range(1, 13):
            tt = t + step
            bump_left[idx] = np.maximum(saved_bump - step, 0)
            # Future trouble: today's, decayed, plus fresh shocks whose spread widens with
            # the horizon; averaged over them with the probit approximation.
            trouble_now[idx] = saved_trouble * RHO ** step
            spread2 = TROUBLE_SD ** 2 * (1 - RHO ** (2 * step))
            pm = sigmoid(logit_first_miss(idx, tt, age + step) / np.sqrt(1 + np.pi * spread2 / 8))
            pm = np.where(acc.fraud[idx], 1.0, pm)
            pc = p_cure(idx, tt)
            pr1 = p_roll(idx, tt, 1)
            pr2 = p_roll(idx, tt, 2)
            pr1 = np.where(acc.fraud[idx], 1.0, pr1)
            pr2 = np.where(acc.fraud[idx], 1.0, pr2)
            pc = np.where(acc.fraud[idx], 0.0, pc)
            exit_ = np.where(inst, P["prepay"][idx] * refi_boost(acc, idx, policy_all, tt), 0.007)
            exit_ = np.where(inst & (term_left[idx] - step <= 0), 1.0, exit_)
            stay = dist[:, 0] * (1 - pm) + dist[:, 1] * pc + dist[:, 2] * pc
            new = np.zeros_like(dist)
            new[:, 0] = stay * (1 - exit_)
            new[:, 4] = dist[:, 4] + stay * exit_
            new[:, 1] = dist[:, 0] * pm + dist[:, 1] * (1 - pc - pr1)
            new[:, 2] = dist[:, 1] * pr1 + dist[:, 2] * (1 - pc - pr2)
            new[:, 3] = dist[:, 3] + dist[:, 2] * pr2
            dist = new
        bump_left[idx] = saved_bump
        trouble_now[idx] = saved_trouble
        return np.where(m0 >= 3, 1.0, dist[:, 3])

    for t in range(T):
        # Accounts opening this month
        opening = (status == 0) & (acc.open_t == t)
        if opening.any():
            o = np.where(opening)[0]
            status[o] = 1
            balance[o] = np.where(revolving[o], 0.0, acc.amount[o])
            payment[o] = np.where(revolving[o], 0.0, first_payment(acc.amount[o], rate[o], acc.term[o], acc.holiday_free[o]))
            payment0[o] = payment[o]
            util[o] = np.where(revolving[o], util_base[o] * 0.6, 0.0)
            balance[o] = np.where(revolving[o], util[o] * limit[o], balance[o])
            pd12_rows.append((o, np.full(len(o), t), pd12_for(o, t, np.zeros(len(o)))))

        act = np.where(status == 1)[0]
        if len(act) == 0:
            continue
        trouble[act] = RHO * trouble[act] + TROUBLE_SD * np.sqrt(1 - RHO ** 2) * rng.normal(0, 1, len(act))
        trouble_now[:] = trouble
        age = t - acc.open_t[act]
        seasoned = age >= 1

        # Income keeps up with inflation, roughly.
        if t % 12 == 0:
            income[act] *= 1.028

        # Variable rates follow the policy rate; fixed-then-variable reset after the fix.
        var_now = (acc.rate_type[act] == "variable") | ((acc.rate_type[act] == "fixed_then_variable") & (age >= acc.fixed_months[act]))
        if var_now.any():
            vi = act[var_now]
            new_rate = policy[t] + acc.margin[vi]
            changed = np.abs(new_rate - rate[vi]) > 1e-9
            rate[vi] = new_rate
            ci = vi[changed & ~revolving[vi]]
            if len(ci):
                payment[ci] = annuity_vec(balance[ci], rate[ci], np.maximum(term_left[ci], 1))

        # Payment holidays: requested April to September 2020 by up-to-date borrowers.
        if 51 <= t <= 56:
            eligible = act[(missed[act] == 0) & ~holiday_used[act] & seasoned & ~acc.shadow[act]]
            p_req = sigmoid(-3.5 - 0.9 * acc.z[eligible] + 0.9 * acc.shock_2020[eligible] + 0.5 * (t <= 53))
            req = eligible[rng.random(len(eligible)) < p_req]
            if len(req):
                length = np.where(rng.random(len(req)) < 0.45, 6, 3)
                holiday_left[req] = length
                holiday_used[req] = True
                term_left[req] += length
                for i, L in zip(req, length):
                    events.append((i, t, "payment_holiday_start", int(L)))

        on_holiday = holiday_left[act] > 0
        free = age <= acc.holiday_free[act]
        sched = np.where(revolving[act], 0.0, payment[act])
        sched = np.where(on_holiday | free | ~seasoned, 0.0, sched)

        lg = logit_first_miss(act, t, age)
        pm = sigmoid(lg)
        pm = np.where(acc.fraud[act], 1.0, pm)
        u = rng.random(len(act))
        m = missed[act].copy()
        paid = np.zeros(len(act))
        r_m = rate[act] / 1200.0

        # Revolving accounts: the balance follows how much of the limit they use, and use
        # drifts up as trouble builds, before the first missed payment.
        if revolving[act].any():
            rv = revolving[act]
            target = util_base[act] + 0.45 * np.clip(trouble[act], 0, None) + 0.35 * sigmoid(lg + 2.0)
            new_util = np.clip(0.65 * util[act] + 0.35 * target + rng.normal(0, 0.05, len(act)), 0.0, 1.04)
            blocked = m >= 2
            new_util = np.where(blocked, util[act], new_util)
            util[act] = np.where(rv, new_util, util[act])
            bal_rv = np.where(blocked, balance[act] * (1 + r_m) + 25.0, util[act] * limit[act])
            balance[act] = np.where(rv, bal_rv, balance[act])
            min_due = np.where(balance[act] > 0, np.maximum(0.025 * balance[act], np.minimum(25.0, balance[act])), 0.0)
            sched = np.where(rv & seasoned & ~on_holiday, min_due, sched)

        due_now = (sched > 0) & seasoned & ~on_holiday & ~free
        # Up to date
        cur = (m == 0) & due_now
        miss_now = cur & (u < pm)
        # Behind, not yet in default
        beh = (m >= 1) & (m <= 2) & due_now
        pc = np.where(acc.fraud[act], 0.0, p_cure(act, t))
        pr = np.where(acc.fraud[act], 1.0, p_roll(act, t, m))
        pr = np.where(bankrupt[act], 1.0, pr)
        cure = beh & (u < pc)
        roll = beh & ~cure & (u < pc + pr)
        # In default
        dfl = (m >= 3)
        post_cure = dfl & ~bankrupt[act] & ~acc.fraud[act] & (u < P["post_cure"][act] * sigmoid(0.5 + 0.6 * acc.z[act]) * 2)
        post_cure = post_cure & (m < P["chargeoff"][act])
        post_roll = dfl & ~post_cure & (rng.random(len(act)) < 0.88)

        new_m = m.copy()
        new_m[miss_now] = 1
        new_m[cure] = 0
        new_m[roll] += 1
        new_m[post_cure] = 0
        new_m[post_roll] += 1
        missed[act] = new_m

        # What was paid
        inst = ~revolving[act]
        paid = np.where(cur & ~miss_now, sched, paid)
        paid = np.where(beh & ~cure & ~roll, sched, paid)
        paid = np.where(cure, sched * (m + 1), paid)
        paid = np.where(post_cure, np.where(inst, payment[act] * (m + 1), sched + 0.2 * balance[act]), paid)
        partial = (miss_now | roll | post_roll) & (rng.random(len(act)) < 0.3)
        paid = np.where(partial, sched * rng.uniform(0.1, 0.6, len(act)), paid)
        if revolving[act].any():
            extra = np.where(transactor[act], balance[act] - sched, (balance[act] - sched) * rng.uniform(0, 0.25, len(act)) ** 2)
            paid = np.where(revolving[act] & (cur & ~miss_now), sched + np.maximum(extra, 0), paid)

        # Balances of instalment accounts
        bal = balance[act]
        bal_inst = np.maximum(bal * (1 + r_m) - paid, 0.0)
        balance[act] = np.where(inst & seasoned, bal_inst, balance[act])
        term_left[act] = np.where(inst & seasoned & ~on_holiday, term_left[act] - 1, term_left[act])

        # Holidays tick down; when one ends the stress it hid starts to show.
        ending = on_holiday & (holiday_left[act] == 1)
        holiday_left[act] = np.maximum(holiday_left[act] - 1, 0)
        bump_left[act] = np.maximum(bump_left[act] - 1, 0)
        bump_left[act[ending]] = 6
        for i in act[ending]:
            events.append((i, t, "payment_holiday_end", 0))

        # Bankruptcy: an unlikeliness-to-pay event before or after missed payments.
        p_bk = np.where(missed[act] >= 1, 0.012, 0.00008) * np.exp(0.4 * stress_all[t])
        bk = ~bankrupt[act] & (rng.random(len(act)) < p_bk) & ~acc.shadow[act]
        bankrupt[act[bk]] = True
        for i in act[bk]:
            events.append((i, t, "bankruptcy", 0))

        # Default: the first month an account reaches three missed payments.
        new_def = (missed[act] >= 3) & ~in_default[act]
        di = act[new_def]
        in_default[di] = True
        first = ~ever_default[di]
        ever_default[di] = True
        default_t[di[first]] = t
        default_age[di[first]] = age[new_def][first]
        for i in di:
            defaults.append((i, t, balance[i], int(missed[i])))
        cured = act[post_cure | (cure & in_default[act])]
        in_default[cured] = False
        for i in act[post_cure]:
            events.append((i, t, "cure_from_default", 0))

        if acc.shadow.any():
            sh = act[acc.shadow[act]]
            shadow_bad[sh[missed[sh] >= 3]] = True

        # Record the month-end row (shadow accounts are not Fernhill's: no row).
        real = act[~acc.shadow[act]]
        if len(real):
            sel = ~acc.shadow[act]
            rows.append((real, np.full(len(real), t), balance[real].copy(), limit[real].copy(),
                         sched[sel].copy(), paid[sel].copy(), missed[real].copy(),
                         (holiday_left[real] > 0) | (on_holiday[sel]), rate[real].copy()))

        # True pd12 for every open account at this month end.
        pd12_rows.append((act, np.full(len(act), t), pd12_for(act, t, age)))

        # Closures
        mature = inst & (term_left[act] <= 0) & (missed[act] == 0) & ~on_holiday
        prep = (missed[act] == 0) & ~on_holiday & seasoned & (rng.random(len(act)) < P["prepay"][act] * refi_boost(acc, act, policy, t))
        prep = prep & ~mature
        co = (missed[act] >= P["chargeoff"][act])
        shadow_done = acc.shadow[act] & (age >= 12)
        card_close = revolving[act] & (missed[act] == 0) & (rng.random(len(act)) < np.where(util[act] < 0.03, 0.012, 0.003))
        # Credit line increases: every six months a card that is up to date, well used and
        # looks good to Fernhill's behaviour checks may get 25% more limit. Its own random
        # stream, so the rest of the book is drawn exactly as before.
        cli = (prod[act] == "card") & (age % 6 == 0) & (age > 0) & (missed[act] == 0) & (util[act] > 0.5)
        cli = cli & (acc.z[act] + cli_rng.normal(0, 0.6, len(act)) > 0.3) & (cli_rng.random(len(act)) < 0.35)
        cli = cli & (limit[act] < 30000)
        if cli.any():
            ci = act[cli]
            limit[ci] = np.minimum(np.round(limit[ci] * 1.25, -2), 30000)
            util[ci] = balance[ci] / limit[ci]
        mort_sale = (prod[act] == "mortgage") & (missed[act] >= 12) & (rng.random(len(act)) < 0.10)
        repo = (prod[act] == "auto") & (missed[act] == 4) & (rng.random(len(act)) < 0.75)
        sme_sec = np.isin(prod[act], ["sme_term"]) & (missed[act] >= 4) & (rng.random(len(act)) < 0.22) & acc.extra["secured"][act]
        prep_inst = prep & inst
        card_close = card_close | (prep & revolving[act])
        prep = prep_inst
        for mask, reason in ((mature, "repaid"), (prep, "prepaid"), (co, "charged_off"),
                             (card_close, "closed_by_customer"), (mort_sale, "property_sold"),
                             (repo, "vehicle_repossessed"), (sme_sec, "collateral_sold"),
                             (shadow_done, "shadow_end")):
            idx = act[mask & (status[act] == 1)]
            if len(idx):
                status[idx] = 2
                for i in idx:
                    closes.append((i, t, reason, balance[i]))
                if reason in ("repaid", "prepaid", "closed_by_customer"):
                    balance[idx] = 0.0

    return dict(rows=rows, events=events, defaults=defaults, closes=closes, pd12=pd12_rows,
                shadow_bad=shadow_bad, default_t=default_t, default_age=default_age,
                months=months, transactor=transactor)


def annuity_vec(principal, annual_rate_pct, months):
    r = np.asarray(annual_rate_pct, dtype=float) / 1200.0
    months = np.maximum(np.asarray(months, dtype=float), 1)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        pay = np.where(r > 0, principal * r / (1 - (1 + r) ** -months), principal / months)
    return np.where(months > 0, pay, 0.0)


def first_payment(principal, annual_rate_pct, months, free_months):
    """The instalment: an annuity over the term, or, for a loan whose first months are
    payment-free, over the months that remain on the balance those free months grew to."""
    free = np.asarray(free_months, dtype=float)
    grown = principal * (1 + np.asarray(annual_rate_pct, dtype=float) / 1200.0) ** free
    return annuity_vec(grown, annual_rate_pct, np.asarray(months, dtype=float) - free)


def refi_boost(acc: Accounts, act: np.ndarray, policy: np.ndarray, t: int) -> np.ndarray:
    """Borrowers refinance when rates fall below what they pay, and stay put when rates
    rise above it."""
    gap = acc.rate[act] - (policy[t] + np.where(acc.product[act] == "mortgage", 2.0, 6.0))
    boost = np.clip(1.0 + 0.35 * gap, 0.4, 2.5)
    return np.where(np.isin(acc.product[act], list(REVOLVING)), 1.0, boost)
