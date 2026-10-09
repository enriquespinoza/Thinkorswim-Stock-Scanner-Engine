from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from dotenv import load_dotenv

from config.settings import PROJECT_ROOT
from src.integrations.schwab.market_data_client import SchwabMarketDataClient


DEFAULT_MAX_TOKEN_AGE_SECONDS = 561_600.0


@dataclass(frozen=True)
class SchwabAuthConfig:
    app_key: str = field(repr=False)
    app_secret: str = field(repr=False)
    callback_url: str
    token_path: Path
    interactive: bool = True
    max_token_age_seconds: float = DEFAULT_MAX_TOKEN_AGE_SECONDS


def _required(environ: Mapping[str, str], name: str) -> str:
    value = str(environ.get(name, "")).strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is not configured.")
    return value


def validate_auth_config(config: SchwabAuthConfig) -> SchwabAuthConfig:
    if not config.app_key.strip():
        raise ValueError("Schwab app key cannot be empty.")
    if not config.app_secret.strip():
        raise ValueError("Schwab app secret cannot be empty.")

    parsed = urlparse(config.callback_url.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("Schwab callback URL must be a valid HTTPS URL.")

    token_path = Path(config.token_path)
    if token_path.suffix.lower() != ".json":
        raise ValueError("Schwab token path must use a .json file.")

    if float(config.max_token_age_seconds) <= 0:
        raise ValueError("max_token_age_seconds must be positive.")

    return config


def load_schwab_auth_config(
    environ: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
    interactive: bool = True,
) -> SchwabAuthConfig:
    project_root = Path(project_root).resolve()

    if environ is None:
        load_dotenv(project_root / ".env", override=False)
        environ = os.environ

    token_path = Path(_required(environ, "SCHWAB_TOKEN_PATH")).expanduser()
    if not token_path.is_absolute():
        token_path = project_root / token_path

    return validate_auth_config(
        SchwabAuthConfig(
            app_key=_required(environ, "SCHWAB_APP_KEY"),
            app_secret=_required(environ, "SCHWAB_APP_SECRET"),
            callback_url=_required(environ, "SCHWAB_CALLBACK_URL"),
            token_path=token_path.resolve(),
            interactive=interactive,
        )
    )


def _load_easy_client() -> Callable[..., Any]:
    try:
        from schwab.auth import easy_client
    except ImportError as exc:
        raise RuntimeError(
            "schwab-py is not installed. Install requirements before Schwab OAuth."
        ) from exc
    return easy_client


def create_schwab_market_data_client(
    config: SchwabAuthConfig,
    auth_factory: Callable[..., Any] | None = None,
) -> SchwabMarketDataClient:
    validate_auth_config(config)
    config.token_path.parent.mkdir(parents=True, exist_ok=True)

    factory = auth_factory or _load_easy_client()
    raw_client = factory(
        api_key=config.app_key,
        app_secret=config.app_secret,
        callback_url=config.callback_url,
        token_path=str(config.token_path),
        asyncio=False,
        enforce_enums=True,
        max_token_age=float(config.max_token_age_seconds),
        interactive=config.interactive,
    )
    if raw_client is None:
        raise RuntimeError("Schwab authentication returned no client.")

    return SchwabMarketDataClient(raw_client)
