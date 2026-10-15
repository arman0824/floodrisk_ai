# Flood Command Center

Production-shaped hackathon prototype for a multi-agent flood risk and
disaster advisory console. It combines a FastAPI streaming backend, a
LangGraph-style agent pipeline, live public weather and incident feeds,
explainable dispatch synthesis, and a Streamlit/Pydeck executive dashboard.

The checked-in `.env.example` enables live public-data mode. Each five-second
cycle fetches current data and records provider health. If a provider is down,
only that provider falls back to deterministic local data and the dashboard
labels the result as `mixed` or `fallback`.

## Quick start

Requirements: Python 3.11+ and a virtual environment. Python 3.11.15 is
pinned in `.python-version`.

```bash
make install
source .venv/bin/activate
cp .env.example .env
make test
```

Start the API and dashboard in separate terminals:

```bash
make api
make dashboard
```

Open <http://localhost:8501> for the dashboard. The API is available at
<http://localhost:8000/docs>.

## Live data sources

When `LIVE_DATA_ENABLED=true`:

- **Open-Meteo Forecast API** supplies current precipitation and wind for the
  expanded Mumbai flood-prone monitoring zones, including Kurla, Sion,
  Dharavi, Hindmata, Wadala, Parel, Chembur, Ghatkopar, Vikhroli, Bhandup,
  Mulund, Powai, Andheri, Jogeshwari, Goregaon, Malad, Kandivali, Borivali,
  Santacruz, Vile Parle, Bandra, Govandi, and Mankhurd.
- **Open-Meteo Flood API** supplies modeled river discharge. The actual
  `river_discharge_m3_s` value is retained, and the risk pipeline separately
  derives a clearly labeled level proxy because this prototype does not have a
  free public Mumbai gauge-height feed.
- **Google News RSS** supplies current public incident reports matching
  `SOCIAL_FEED_QUERY`. These are public reports, not authenticated X/Twitter
  posts.

Every API status includes `data_mode` and `data_sources`, including provider
health, latency, and fallback details.

## Docker

```bash
docker compose up --build
```

The dashboard runs on port 8501 and the API runs on port 8000. Docker is not
required for the offline test suite.

## Optional integrations

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to enable optional LLM
summaries. The risk calculation and the fallback summaries remain local and
deterministic if the key is missing or an API call fails.

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
an API key, Docker, or internet access.
