"""Application configuration.

Speech is handled entirely by Sarvam AI: Saaras for speech-to-text and Bulbul for
text-to-speech. Structured extraction is deterministic and runs offline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = _env(name, "").lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return default


@dataclass(frozen=True)
class Settings:
    var_dir: Path
    database_url: str
    upload_dir: Path
    tts_dir: Path
    cors_origins: list[str]
    max_upload_mb: int
    log_level: str

    sarvam_api_key: str = field(repr=False)
    sarvam_base_url: str
    stt_provider: str
    tts_provider: str

    audio_preprocessing_enabled: bool
    geocoding_enabled: bool

    @property
    def sarvam_key_configured(self) -> bool:
        return bool(self.sarvam_api_key)


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174",
)


def load_settings() -> Settings:
    var_dir = Path(_env("AAPDA_VAR_DIR", str(BACKEND_DIR / "var"))).resolve()
    db_url = _env("DATABASE_URL", f"sqlite:///{(var_dir / 'aapda.db').as_posix()}")
    origins = [o.strip() for o in _env("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",") if o.strip()]

    return Settings(
        var_dir=var_dir,
        database_url=db_url,
        upload_dir=var_dir / "uploads",
        tts_dir=var_dir / "tts",
        cors_origins=origins,
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 10),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        sarvam_api_key=_env("SARVAM_API_KEY"),
        sarvam_base_url=_env("SARVAM_BASE_URL", "https://api.sarvam.ai").rstrip("/"),
        stt_provider=_env("STT_PROVIDER", "auto").lower(),
        tts_provider=_env("TTS_PROVIDER", "auto").lower(),
        audio_preprocessing_enabled=_env_bool("AUDIO_PREPROCESSING_ENABLED", False),
        geocoding_enabled=_env_bool("GEOCODING_ENABLED", False),
    )


settings = load_settings()
