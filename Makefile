# Requires Python 3.10–3.13 on PATH as python3 (override: make setup PYTHON=python3.11)
PYTHON ?= python3
BIN := .venv/bin

.PHONY: setup run test analytics dashboard docs explore clean

setup:
	$(PYTHON) -m venv .venv
	$(BIN)/pip install --quiet -r requirements.txt

run:            ## ingest -> dbt build (models + tests) -> validation report
	$(BIN)/python src/ingest.py
	cd dbt && DBT_PROFILES_DIR=. ../$(BIN)/dbt build
	$(BIN)/python src/validate.py

analytics:      ## print answers to the 9 analytics questions
	$(BIN)/python src/run_analytics.py

test:
	PATH="$(CURDIR)/$(BIN):$$PATH" $(BIN)/python -m pytest tests -q

dashboard:
	$(BIN)/streamlit run dashboard/app.py

docs:           ## lineage graph + model/column docs at localhost:8080
	cd dbt && DBT_PROFILES_DIR=. ../$(BIN)/dbt docs generate && ../$(BIN)/dbt docs serve

explore:        ## browse the tables in the DuckDB UI (read-only)
	$(BIN)/python src/explore.py

clean:
	rm -rf data/processed/* dbt/target dbt/logs
