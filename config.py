"""Environment-backed settings with safe defaults for a live demo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a convenience dependency
    pass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    city: str = "Mumbai"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    stream_interval_seconds: float = 5.0
    live_data_enabled: bool = False
    live_data_timeout_seconds: float = 8.0
    social_feed_query: str = "Mumbai flood OR waterlogging OR heavy rain"
    api_base_url: str = "http://localhost:8000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        city=os.getenv("CITY", "Mumbai"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        stream_interval_seconds=float(os.getenv("STREAM_INTERVAL_SECONDS", "5")),
        live_data_enabled=_as_bool(os.getenv("LIVE_DATA_ENABLED"), False),
        live_data_timeout_seconds=float(os.getenv("LIVE_DATA_TIMEOUT_SECONDS", "8")),
        social_feed_query=os.getenv("SOCIAL_FEED_QUERY", "Mumbai flood OR waterlogging OR heavy rain"),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
