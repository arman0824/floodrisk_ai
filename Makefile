PYTHON ?= .venv/bin/python
SYSTEM_PYTHON ?= python3.11

.PHONY: install test api dashboard docker-build docker-up

install:
	@if [ ! -x "$(PYTHON)" ]; then $(SYSTEM_PYTHON) -m venv .venv; fi
	$(PYTHON) -m pip install -r requirements.lock

test:
	$(PYTHON) -m pytest -q

api:
	$(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dashboard:
	$(PYTHON) -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501

docker-build:
	docker build -t flood-command-center .

docker-up:
	docker compose up --build
