"""Configuration for the news summarizer.

Reads settings from environment variables (loaded from a local .env file)
and exposes them through a single Config object via get_config().
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

REQUIRED_KEYS = ("OPENAI_API_KEY", "COHERE_API_KEY", "NEWS_API_KEY")


@dataclass(frozen=True)
class Config:
    """Application settings. Attribute names are lowercase on purpose."""

    openai_api_key: str
    cohere_api_key: str
    news_api_key: str
    environment: str
    max_retries: int
    request_timeout: int
    daily_budget: float


def _read_key(name: str) -> str:
    """Return an env var, or "" if it is unset, empty, or still a placeholder."""
    value = os.getenv(name, "").strip()
    if value.startswith("<") and value.endswith(">"):
        return ""
    return value


def _read_number(name: str, default, cast):
    """Return an env var converted with `cast`, or raise a clear error."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        raise ValueError(f"{name} must be a {cast.__name__}, got {raw!r}") from None


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Build the Config once, validate it, and reuse it afterwards."""
    missing = [name for name in REQUIRED_KEYS if not _read_key(name)]
    if missing:
        raise ValueError(
            "Missing required configuration: " + ", ".join(missing)
            + ". Set them in your .env file."
        )

    return Config(
        openai_api_key=_read_key("OPENAI_API_KEY"),
        cohere_api_key=_read_key("COHERE_API_KEY"),
        news_api_key=_read_key("NEWS_API_KEY"),
        environment=os.getenv("ENVIRONMENT", "development").strip(),
        max_retries=_read_number("MAX_RETRIES", 3, int),
        request_timeout=_read_number("REQUEST_TIMEOUT", 30, int),
        daily_budget=_read_number("DAILY_BUDGET", 5.00, float),
    )


if __name__ == "__main__":
    try:
        config = get_config()
    except ValueError as error:
        print(f"❌ {error}")
        raise SystemExit(1)

    print("✅ Configuration is valid")
    print(f"   environment:     {config.environment}")
    print(f"   max_retries:     {config.max_retries}")
    print(f"   request_timeout: {config.request_timeout}s")
    print(f"   daily_budget:    ${config.daily_budget:.2f}")
    print("   API keys:        OpenAI, Cohere, News API all set")
