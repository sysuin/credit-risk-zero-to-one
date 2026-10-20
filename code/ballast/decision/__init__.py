"""Ballast decides: from an application to a decision (Chapter 11).

    policy.py    Fernhill's lending policy as written down: the rules
                 that decline before any score, Mark I's points table,
                 the cut-off history, amounts, card limits and line
                 increases
    strategy.py  strategy curves, swap sets, choosing a cut-off and a
                 refer band, what a loan earns, test sizes
    engine.py    one function per application: rules, score, cut-off
                 or refer, amount, reasons
"""
