PYTHON ?= .venv/bin/python
SYSTEM_PYTHON ?= python3.11
APP_PATH ?= src

.PHONY: install test api dashboard docker-build docker-up

install:
	@if [ ! -x "$(PYTHON)" ]; then $(SYSTEM_PYTHON) -m venv .venv; fi
	$(PYTHON) -m pip install -r requirements.lock

test:
	PYTHONPATH=$(APP_PATH) LIVE_DATA_ENABLED=false $(PYTHON) -m pytest -q

api:
	PYTHONPATH=$(APP_PATH) $(PYTHON) -m uvicorn flood_command_center.main:app --host 0.0.0.0 --port 8000 --reload

dashboard:
	PYTHONPATH=$(APP_PATH) $(PYTHON) -m streamlit run src/flood_command_center/app.py --server.address 0.0.0.0 --server.port 8501

docker-build:
	docker build -t flood-command-center .

docker-up:
	docker compose up --build
