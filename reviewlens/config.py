"""Runtime settings loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Bump whenever a prompt changes; it is part of the cache key and the eval report.
PROMPT_VERSION = "v3"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "gpt-4o-mini"))
    temperature: float = 0.0
    request_timeout: int = field(default_factory=lambda: _int("REQUEST_TIMEOUT", 60))

    business_name: str = field(default_factory=lambda: os.getenv("BUSINESS_NAME") or "Spice Route Kitchen")
    support_contact: str = field(default_factory=lambda: os.getenv("SUPPORT_CONTACT", "").strip())

    max_concurrency: int = field(default_factory=lambda: _int("MAX_CONCURRENCY", 5))
    chunk_size: int = field(default_factory=lambda: _int("CHUNK_SIZE", 25))

    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 5))
    max_rows: int = field(default_factory=lambda: _int("MAX_ROWS", 1000))
    max_runs_per_session: int = field(default_factory=lambda: _int("MAX_RUNS_PER_SESSION", 10))
    daily_run_cap: int = field(default_factory=lambda: _int("DAILY_RUN_CAP", 50))

    access_code: str = field(default_factory=lambda: os.getenv("ACCESS_CODE", "").strip())

    cache_dir: Path = ROOT / ".cache"
    log_dir: Path = ROOT / "logs"
    prompt_version: str = PROMPT_VERSION

    # USD per 1M tokens (input, output); used only for cost estimates in logs.
    price_per_million: tuple[float, float] = (0.15, 0.60)


def get_settings() -> Settings:
    return Settings()
