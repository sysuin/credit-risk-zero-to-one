# Credit Risk from Zero to One: the code

The companion code for *Credit Risk from Zero to One: Lending, Scoring and Risk Management with Python* by Sunny Singh,
part of the Zero to One Series.

It holds **Ballast**, the credit risk platform the book builds across thirty-one
chapters, and every listing in the book with the output it printed. Ballast belongs to
Fernhill Bank, a fictional mid-sized lender with consumer, small-business and commercial
books. Its loan book — ten years of applications, accounts and monthly performance, with
recoveries, a commercial book with accounts, ratings and share prices, and the economy
they lived through — is generated here from a fixed seed, together with a separate truth
database of what a simulator knows and a bank never can.

Nothing in the book's output was typed by hand. Each listing was executed and its real
output saved beside it, so you can compare what you get with what the book shows. Every
listing is deterministic: run it twice and it prints the same thing, to the last digit.

## Start

You need Python 3.12 and about 1 GB of free disk. No cloud account, no API key.

```bash
make setup                   # a virtualenv in .venv, the libraries, and code/ on Python's path
make data                    # Fernhill's loan book, generated and verified (a minute or two)
make preflight               # checks Python, the libraries and the data, in order
```

`make data` needs no network: the loan book is generated from a fixed seed, identical on
every machine. On macOS, LightGBM needs OpenMP (`brew install libomp`). Appendix A of the
book walks through setup on macOS, Windows and Linux.

## Running the listings

Each chapter's listings are in `code/NN/`, numbered in the order the chapter runs them,
with the captured output beside each one as a `.out` file. Run one from the repository's
root, because every path in the book is written from there:

```bash
.venv/bin/python code/01/02_charge_offs.py
```

Or let the runner run a chapter and compare its output with what the book printed:

```bash
.venv/bin/python code/_runner.py 07                 # re-run chapter 7, capture its output
.venv/bin/python code/_runner.py --check --twice    # every capture current, every run repeatable
```

Some listings later in the book read results that earlier chapters saved under
`data/ballast/`; run the chapters in order the first time. `requirements.txt` gives lower
bounds; Appendix C of the book lists the exact versions the printed output came from.

## Running Ballast

```bash
make run          # Ballast v1.0: everything from the loan book, reconciled (a minute or more)
make run-check    # check that every saved result exists and agrees with its chapter
make help         # everything else
```

## Where things are

```
code/NN/            the listings for chapter NN, each with its captured .out
code/ballast/       Ballast: loan arithmetic, performance, scorecards, decisions, pricing,
                    commercial credit, PD/LGD/EAD, provisions, capital, portfolio,
                    validation, monitoring, collections, stress, appetite, governance
code/fernhill/      the simulator that generates Fernhill's loan book, and its checks
tests/              the test suite
```

## Licence

MIT; see [LICENSE](LICENSE). The licence covers this code and the data it generates, not
the book. Fernhill Bank, Meridian Supply Co. and every borrower, loan and figure in the
data are fictional.
