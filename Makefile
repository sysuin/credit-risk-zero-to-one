# Ballast — the commands you will actually type.
#
# Ballast is built across the book, so some of its commands arrive later than others.
# Those say which chapter brings them rather than failing with a missing file.

.DEFAULT_GOAL := help
.PHONY: help setup preflight data verify-data listings verify test lint clean

PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
export PYTHONPATH := $(CURDIR)/code

help:  ## show this list
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'

setup:  ## create the virtualenv and install everything
	@if [ -x .venv/bin/python ]; then \
	  echo "Keeping the existing .venv ($$(.venv/bin/python --version))."; \
	else echo "$(PY) -m venv .venv"; $(PY) -m venv .venv; fi
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/python code/_path.py
	@echo "Now: make data, then make preflight."

preflight:  ## check Python, the libraries and the loan book before you start
	$(PY) code/_preflight.py

data:  ## generate Fernhill's loan book from its seed, and verify it (under a minute)
	$(PY) code/fernhill/generate.py
	$(PY) code/fernhill/verify.py

verify-data:  ## check the loan book has every property the chapters rely on
	$(PY) code/fernhill/verify.py

listings:  ## run every listing whose source changed, and capture its output
	$(PY) code/_runner.py

verify:  ## the code guarantee: nothing stale, and every listing prints the same thing twice
	$(PY) code/_runner.py --check --twice

test:  ## the test suite
	$(PY) -m pytest tests/ -q

lint:  ## the checks CI runs
	$(PY) -m ruff check code/ tests/
	$(PY) code/_runner.py --check

clean:  ## remove build output, caches and the sandbox
	rm -rf .pytest_cache/ .ruff_cache/ data/sandbox/
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

.PHONY: run run-check
run:  ## Ballast v1.0: everything from the loan book, reconciled (Ch 31; a minute or more)
	$(PY) -m ballast.run

run-check:  ## check that every saved result exists and agrees with its chapter (seconds)
	$(PY) -m ballast.run --check
