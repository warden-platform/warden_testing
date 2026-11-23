PYTHON ?= python3.13
VENV := .venv
PYTEST := $(VENV)/bin/python -m pytest

.PHONY: install stack-up stack-down test smoke connector security approval html report clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

stack-up:
	scripts/stack_up.sh

stack-down:
	scripts/stack_down.sh

test:
	$(PYTEST) --alluredir=allure-results --clean-alluredir

smoke:
	$(PYTEST) -m smoke --alluredir=allure-results --clean-alluredir

connector:
	$(PYTEST) -m connector --alluredir=allure-results --clean-alluredir

security:
	$(PYTEST) -m security --alluredir=allure-results --clean-alluredir

approval:
	$(PYTEST) -m approval --alluredir=allure-results --clean-alluredir

html:
	$(PYTEST) --html=report/warden-test-report.html --self-contained-html --alluredir=allure-results --clean-alluredir

report:
	allure serve allure-results

clean:
	rm -rf .pytest_cache allure-results allure-report report
	find . -type d -name __pycache__ -prune -exec rm -rf {} +