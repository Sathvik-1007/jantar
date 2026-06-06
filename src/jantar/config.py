"""Application configuration — single source of truth for all settings.

Settings are loaded from environment variables and a `.env` file at the
project root. The `.env` path is resolved ABSOLUTELY from this module's
location, so the application behaves identically regardless of the current
working directory it is launched from (a CLI run from `$HOME` and a server
run from the project dir read the exact same configuration).

Responsibilities:
- Define every tunable as a typed field with a documented default.
- Resolve the `.env` and log-file locations to absolute paths.
- Configure process-wide logging (console + rotating-safe file handler).

NOT responsible for: secret rotation, runtime reconfiguration, or validating
the *semantic* correctness of external endpoints (that is the caller's job).
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = three parents up from this file:
#   src/jantar/config.py -> src/jantar -> src -> <project root>
# The `.env` and `logs/` directories live at the project root.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_ENV_FILE: Path = PROJECT_ROOT / ".env"

# Loggers from third-party libraries that flood output at INFO level.
# We pin them to WARNING so the signal (jantar.* logs) is not buried.
_NOISY_LOGGERS: tuple[str, ...] = (
    "httpx",
    "httpcore",
    "huggingface_hub",
    "sentence_transformers",
    "FlagEmbedding",
    "transformers",
    "urllib3",
    "filelock",
)


class Settings(BaseSettings):
    """Typed application settings, populated from env vars / `.env`.

    Every field has a safe default so the object always constructs; callers
    that require a value (e.g. the Sarvam key) validate presence at the point
    of use and fail with a clear, actionable error rather than a cryptic one.
    """

    # Sarvam AI — primary LLM + translation/STT/TTS provider.
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"

    # data.gov.in — open government datasets (optional; tools degrade if unset).
    data_gov_api_key: str = ""

    # Qdrant — vector store for tool + knowledge retrieval.
    qdrant_url: str = "http://localhost:6333"

    # HTTP server bind address.
    host: str = "0.0.0.0"
    port: int = 8000

    # REST API authentication key. Empty => API auth fails closed (deny all).
    api_key: str = ""

    # Logging configuration.
    log_level: str = "INFO"
    log_file: str = "logs/jantar.log"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "sarvam_api_key",
        "data_gov_api_key",
        "api_key",
        mode="after",
    )
    @classmethod
    def _strip_secret(cls, value: str) -> str:
        """Strip surrounding whitespace from secrets.

        A trailing newline/space in a `.env` value produces malformed HTTP
        auth headers (e.g. ``Bearer abc\\n``) that some clients reject with an
        opaque ``Illegal header value`` error. Stripping at load time prevents
        that entire failure class.
        """
        return value.strip()

    @property
    def log_file_path(self) -> Path:
        """Absolute path to the log file.

        A relative ``log_file`` is resolved against the project root so logs
        land in a single, predictable location regardless of launch cwd.
        """
        p = Path(self.log_file)
        return p if p.is_absolute() else PROJECT_ROOT / p


settings = Settings()


def _configure_logging() -> None:
    """Configure process-wide logging: console + file, with noise suppression.

    Idempotent — safe to call more than once (handlers are reset each time).
    """
    log_path = settings.log_file_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # Reset handlers so repeated calls (e.g. tests, reload) don't duplicate output.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Silence chatty third-party loggers — keep jantar.* signal visible.
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


_configure_logging()
