"""Process settings read from the environment (.env). Team-owned numbers live in config/*.yaml instead."""

import os
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None or v == "" else v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/rakshasetu"))
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", True))
    public_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_URL", ""))
    secret_key: str = field(default_factory=lambda: os.environ.get("SECRET_KEY", "dev-only-change-me"))
    config_dir: Path = field(default_factory=lambda: Path(os.environ.get("CONFIG_DIR", API_ROOT / "config")))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DATA_DIR", API_ROOT.parent.parent / "data")))
    contracts_dir: Path = field(default_factory=lambda: Path(os.environ.get(
        "CONTRACTS_DIR", API_ROOT.parent.parent / "packages" / "contracts")))
    files_dir: Path = field(default_factory=lambda: Path(os.environ.get("FILES_DIR", API_ROOT.parent.parent / "var" / "files")))


def get_settings() -> Settings:
    return Settings()
