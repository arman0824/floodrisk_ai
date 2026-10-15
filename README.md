# Flood Command Center

Production-shaped hackathon prototype for a multi-agent flood risk and
disaster advisory console. It combines a FastAPI streaming backend, a
LangGraph-style agent pipeline, deterministic mock telemetry/social feeds,
OpenCV flood-depth simulation, and a Streamlit/Pydeck executive dashboard.

The default mode is deterministic and works without API keys or network
access at runtime. An optional OpenAI summarization layer and optional local
YOLOv8n weights can be enabled through environment variables.

## Quick start

Requirements: Python 3.11+ and a virtual environment. Python 3.11.15 is
pinned in `.python-version`.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
make install
cp .env.example .env
make test
```

Start the API and dashboard in separate terminals:

```bash
make api
make dashboard
```

Open <http://localhost:8501> for the dashboard. The API is available at

## Docker

```bash
docker compose up --build
```

The dashboard runs on port 8501 and the API runs on port 8000. Docker is not
required for the deterministic test suite.

## Optional integrations

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to enable optional LLM
summaries. The risk calculation and the fallback summaries remain local and
deterministic if the key is missing or an API call fails.

To use a pre-downloaded YOLOv8n model, put it at
downloads model weights during startup.

## API endpoints

- `GET /api/health` — service health and mode information.
- `GET /api/latest` — latest complete status snapshot.
- `GET /api/live-status` — Server-Sent Events stream of status updates.
- `POST /api/broadcast` — records a simulated SMS broadcast.

## Testing

```bash
make test
```

Tests are designed to run against deterministic local data and do not require
an API key, model weights, Docker, or internet access.
