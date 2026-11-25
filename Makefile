PYTHON ?= python3

.PHONY: verify test reproduce figures
verify:
	$(PYTHON) reproduce.py --verify-only

test:
	$(PYTHON) -m unittest discover -s tests -v

reproduce:
	$(PYTHON) reproduce.py --no-figures

figures:
	$(PYTHON) reproduce.py
