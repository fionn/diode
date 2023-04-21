SHELL = /bin/bash
SRC = diode
VENV = venv

venv: requirements.txt
	@python3 -m venv $@ --prompt $@::srl
	@source $@/bin/activate && pip install -r $<
	@echo "enter virtual environment: source $@/bin/activate"

.PHONY: setup_dev
setup_dev: requirements_dev.txt venv
	@(source $(VENV)/bin/activate && pip install -r $<)

.PHONY: install_dev
install_dev: setup_dev
	@(source $(VENV)/bin/activate && pip install --no-deps -e .[dev])
	@echo "enter virtual environment: source venv/bin/activate"

.PHONY: install
install: requirements.txt $(SRC)
	@pip install --user --require-hashes -r $<
	@pip install --user --no-deps .

.PHONY: build
build: $(SRC)
	@python -m build

.PHONY: test
test: $(SRC)
	@source $(VENV)/bin/activate && cd $(SRC)/ && python3 -m unittest

tags: $(SRC)
	@ctags --languages=python --python-kinds=-i -R $(SRC)/

.PHONY: outdated
outdated: $(VENV)
	@(source $(VENV)/bin/activate && pip list --outdated)

.PHONY: lint
lint:
	@find . -iname "*.py" -a -not -path "./venv/*" | xargs pylint --rcfile=.pylintrc

.PHONY: typecheck
typecheck:
	@mypy $(SRC)
